"""Tool-free structured interpretation via existing local provider installations."""
import json
import re
import http.client
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import threading
from urllib.parse import urlsplit
import urllib.request
import urllib.error
from pydantic import ValidationError

OLLAMA = "http://127.0.0.1:11434"
MAX_OUTPUT = 200_000
CODEX_DEFAULT_MODEL = 'gpt-5.6-sol'
CODEX_REASONING_EFFORT = 'high'


class ProviderFailure(ValueError):
    def __init__(self,message,retryable=False):
        super().__init__(message);self.retryable=retryable


def converter_env(provider):
    keys = {"HOME", "PATH", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}
    keys |= {"CODEX_HOME", "OPENAI_API_KEY"} if provider == "codex" else {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR"}
    return {k: v for k, v in os.environ.items() if k in keys}


def provider_status():
    models = []
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=2) as response:
            models = [m["name"] for m in json.loads(response.read(MAX_OUTPUT))["models"]]
        ollama_note = "Local inference; choose an installed model." if models else "Ollama is running but no model is installed. No download is performed."
    except (OSError, ValueError, KeyError):
        ollama_note = "Start Ollama and install a model separately."
    return {"providers": [
        {"id": "codex", "name": "Codex CLI", "available": bool(shutil.which("codex")), "models": [], "remote": True, "note": f"Default: {CODEX_DEFAULT_MODEL} · {CODEX_REASONING_EFFORT} reasoning. Uses existing CLI login; model field overrides the model."},
        {"id": "ollama", "name": "Ollama · local", "available": bool(models), "models": models, "remote": False, "note": ollama_note},
        {"id": "claude", "name": "Claude Code CLI", "available": bool(shutil.which("claude")), "models": [], "remote": True, "note": "Install/sign in separately. Managed hooks or MCP policies are not supported."}]}


def cli_command(provider, workspace, model, schema_path, answer_path):
    executable = shutil.which(provider) or provider
    if provider == "codex":
        command = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "--cd", str(workspace), "--output-schema", str(schema_path), "-o", str(answer_path), "--color", "never"]
        for feature in ("shell_tool", "unified_exec", "hooks", "apps", "plugins", "browser_use", "computer_use", "in_app_browser", "image_generation", "view_image", "skill_search", "multi_agent"):
            command += ["--disable", feature]
        command += ["-c", 'web_search="disabled"']
    else:
        command = [executable, "-p", "--output-format", "json", "--json-schema", schema_path.read_text() if schema_path.exists() else "{}", "--tools", "", "--disallowedTools", "mcp__*", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "", "--settings", '{"disableAllHooks":true}', "--disable-slash-commands", "--no-session-persistence", "--max-turns", "2", "--system-prompt", "Return the requested JSON only. No tools or file access."]
    if provider == 'codex':
        command += ['--model',model or CODEX_DEFAULT_MODEL,'-c',f'model_reasoning_effort="{CODEX_REASONING_EFFORT}"']
    elif model:
        command += ["--model", model]
    if provider == "codex":
        command.append("-")
    return command


def run_process(command, prompt, cwd, env, cancel, timeout=180):
    if cancel.is_set():
        raise InterruptedError("Search cancelled.")
    # Dedicated files avoid pipe deadlocks and permit an output-size bound.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as inp:
        inp.write(prompt.encode()); inp.seek(0)
        process = subprocess.Popen(command, stdin=inp, stdout=out, stderr=err, cwd=cwd, env=env, start_new_session=True)
        start = time.monotonic()
        try:
            while process.poll() is None:
                if cancel.wait(.1):
                    raise InterruptedError("Search cancelled.")
                if time.monotonic() - start > timeout:
                    raise ValueError("Model conversion timed out; try a shorter query or a different model.")
                if out.tell() + err.tell() > MAX_OUTPUT * 4:
                    raise ValueError("Model output exceeded the safety limit.")
            out.seek(0)
            answer = out.read(MAX_OUTPUT + 1).decode(errors="replace")
            if process.returncode:
                # CLI diagnostics can contain account/config details: do not echo them.
                err.seek(0);diagnostics=err.read(MAX_OUTPUT).decode(errors='replace').lower()
                transient=bool(re.search(r'stream disconnected|connection reset|connection closed|econnreset|connection timed out|502 bad gateway|503 service unavailable',diagnostics))
                if transient:raise ProviderFailure('Provider connection was interrupted. Retry the request; no cloud fallback was used.',retryable=True)
                raise ProviderFailure("Provider CLI failed. Check its login, model access and supported isolation flags in a separate terminal.")
            if len(answer.encode()) > MAX_OUTPUT:
                raise ValueError("Model output exceeded the safety limit.")
            return answer
        finally:
            # The session leader may exit before its children. Finish cleanup of
            # this owned group regardless of leader state; never target other jobs.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            else:
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
                # Do not use killpg(..., 0): macOS can reject the existence
                # probe after the leader is reaped. Escalate owned descendants
                # even if the leader exited; ESRCH simply means no group remains.
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            process.wait(timeout=2)


def transport(schema, prompt, provider, model, cancel):
    if cancel.is_set():
        raise InterruptedError("Search cancelled.")
    if provider == "ollama":
        available = next(p for p in provider_status()["providers"] if p["id"] == "ollama")
        if not model or model not in available["models"]:
            raise ValueError("Choose an installed Ollama model. This application never downloads models automatically.")
        payload = {"model": model, "format": schema, "stream": True, "messages": [{"role": "user", "content": prompt}], "options": {"temperature": 0, "num_predict": 10000}}
        parsed = urlsplit(OLLAMA)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=180)
        finished = threading.Event()
        deadline = time.monotonic() + 180
        try:
            connection.request("POST", "/api/chat", body=json.dumps(payload), headers={"Content-Type": "application/json"})
            owned_socket = connection.sock
            def interrupt():
                while not finished.wait(.05):
                    if cancel.is_set() or time.monotonic() > deadline:
                        try:
                            owned_socket.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        return
            threading.Thread(target=interrupt, daemon=True, name="atlas-ollama-cancel").start()
            with connection.getresponse() as response:
                if response.status != 200:
                    raise ValueError("Ollama rejected the generation request. Check the installed model.")
                pieces, size, start = [], 0, time.monotonic()
                for raw in response:
                    if cancel.is_set():
                        raise InterruptedError("Search cancelled.")
                    if time.monotonic() - start > 180:
                        raise ValueError("Model conversion timed out.")
                    chunk = json.loads(raw)
                    if chunk.get("error"):
                        raise ValueError("Ollama could not generate this response. Check the model in its terminal.")
                    value = chunk.get("message", {}).get("content", "")
                    size += len(value.encode())
                    if size > MAX_OUTPUT:
                        raise ValueError("Model output exceeded the safety limit.")
                    pieces.append(value)
                if cancel.is_set():
                    raise InterruptedError("Search cancelled.")
                if time.monotonic() > deadline:
                    raise ValueError("Model conversion timed out.")
                return "".join(pieces)
        except (OSError, http.client.HTTPException) as exc:
            if cancel.is_set():
                raise InterruptedError("Search cancelled.") from exc
            raise ValueError("Ollama is unavailable or timed out. No cloud fallback was used.") from exc
        finally:
            finished.set()
            connection.close()
    if not shutil.which(provider):
        raise ValueError(f"{provider} CLI is not installed. Select another provider or install it separately.")
    if provider == "claude" and any(p.exists() for p in (
        Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
        Path("/etc/claude-code/managed-settings.json"))):
        raise ValueError("Claude managed policies may force hooks/tools. This converter requires an unmanaged, tool-free CLI.")
    with tempfile.TemporaryDirectory(prefix="atlas-converter-") as folder:
        workspace = Path(folder)
        schema_path, answer_path = workspace / "schema.json", workspace / "answer.json"
        schema_path.write_text(json.dumps(schema))
        for attempt in range(2):
            try:
                output = run_process(cli_command(provider, workspace, model, schema_path, answer_path), prompt, workspace, converter_env(provider), cancel)
                break
            except ProviderFailure as exc:
                if attempt or not exc.retryable:raise
                if cancel.wait(.2):raise InterruptedError('Search cancelled.')
        if provider == "codex":
            if not answer_path.exists() or answer_path.stat().st_size > MAX_OUTPUT:
                raise ValueError("Codex returned no bounded structured answer.")
            return answer_path.read_text()
        wrapper = json.loads(output)
        if wrapper.get("is_error") or "structured_output" not in wrapper:
            raise ValueError("Claude returned no structured answer. Check login and model support.")
        return json.dumps(wrapper["structured_output"])


def strict_schema(schema):
    # Codex structured output requires every property listed as required. Pydantic
    # defaults still support convenient application-side construction.
    if isinstance(schema, dict):
        result = {k: strict_schema(v) for k, v in schema.items() if k != "default"}
        # Structured-output providers do not accept JSON Schema prefixItems.
        # Our fixed tuples are homogeneous (e.g. two distinct net aliases).
        # Preserve their length/type contract using ordinary array items.
        if 'prefixItems' in result:
            members=result.pop('prefixItems')
            if not members or any(member != members[0] for member in members):
                raise ValueError('Structured output requires homogeneous tuple fields.')
            result['items']=members[0]
            result['minItems']=result['maxItems']=len(members)
        if result.get("type") == "object" and "properties" in result:
            result["required"] = list(result["properties"])
            result["additionalProperties"] = False
        return result
    if isinstance(schema, list):
        return [strict_schema(v) for v in schema]
    return schema


def validated_generate(contract, prompt, provider, model, cancel, transport=transport):
    schema = strict_schema(contract.model_json_schema())
    instruction = prompt + "\nReturn only JSON matching this schema:\n" + json.dumps(schema)
    for attempt in range(2):
        answer = transport(schema, instruction, provider, model, cancel)
        try:
            return contract.model_validate_json(answer)
        except (ValidationError, ValueError) as exc:
            if attempt:
                raise ValueError("Provider did not produce valid search JSON after one repair. Nothing was queried.") from exc
            # Only validation diagnostics, not model text, are added as instructions.
            details = [{"location": list(e["loc"]), "error": e["type"]} for e in exc.errors()] if isinstance(exc, ValidationError) else []
            instruction = prompt + "\nThe previous output was invalid. Correct these schema errors: " + json.dumps(details) + "\nSchema:\n" + json.dumps(schema)
