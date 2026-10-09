import json
import sys
import threading
import pytest


def test_converter_environment_excludes_database_and_project_secrets(monkeypatch):
    from circuit_workbench.nl_providers import converter_env
    monkeypatch.setenv("NEO4J_PASSWORD", "never-send")
    monkeypatch.setenv("CIRCUIT_STATE", "/private/state")
    monkeypatch.setenv("OTHER_PRIVATE_TOKEN", "never-send")
    env = converter_env("codex")
    assert "NEO4J_PASSWORD" not in env and "CIRCUIT_STATE" not in env
    assert "OTHER_PRIVATE_TOKEN" not in env
    assert "PATH" in env and "HOME" in env


def test_validation_repairs_once_then_rejects_bad_model_output():
    from circuit_workbench.nl_providers import validated_generate
    from circuit_workbench.nl_schema import SearchPlan
    responses = iter(['{"cypher":"DELETE c"}', '{"count_constraints":[{"entity":"resistor","operator":"eq","value":2}]}'])
    result = validated_generate(SearchPlan, "request", "codex", "", threading.Event(), transport=lambda *a: next(responses))
    assert result.count_constraints[0].value == 2
    responses = iter(['{"cypher":"DELETE c"}']*2)
    with pytest.raises(ValueError, match="valid search JSON"):
        validated_generate(SearchPlan, "request", "codex", "", threading.Event(), transport=lambda *a: next(responses))


def test_owned_process_timeout_and_cancellation(tmp_path):
    from circuit_workbench.nl_providers import run_process
    with pytest.raises(ValueError, match="timed out"):
        run_process([sys.executable, "-c", "import time; time.sleep(10)"], "", tmp_path, {}, threading.Event(), timeout=.1)
    event = threading.Event()
    event.set()
    with pytest.raises(InterruptedError):
        run_process([sys.executable, "-c", "print('unused')"], "", tmp_path, {}, event)


def test_cli_builders_disable_tools_without_shell_interpolation(tmp_path):
    from circuit_workbench.nl_providers import cli_command
    cmd = cli_command("codex", tmp_path, "gpt-test", tmp_path/"schema.json", tmp_path/"answer.json")
    assert "read-only" in cmd and "--ephemeral" in cmd and "--ignore-user-config" in cmd
    assert "shell_tool" in cmd and "--output-schema" in cmd
    cmd = cli_command("claude", tmp_path, "", tmp_path/"schema.json", tmp_path/"answer.json")
    assert "--tools" in cmd and "" == cmd[cmd.index("--tools")+1]
    assert "--strict-mcp-config" in cmd and "--setting-sources" in cmd


def test_jobs_return_result_and_cancel_without_accepting_second_active_job():
    from circuit_workbench.nl_jobs import SearchJobs
    release = threading.Event()
    def execute(request, cancel, progress):
        progress("interpreting")
        while not release.wait(.01):
            if cancel.is_set():
                raise InterruptedError()
        return {"items": ["real"]}
    jobs = SearchJobs(execute)
    first = jobs.start({})
    with pytest.raises(ValueError, match="already running"):
        jobs.start({})
    jobs.cancel(first["id"])
    release.set()
    for _ in range(100):
        if jobs.get(first["id"])["state"] not in {"running", "queued"}:
            break
        threading.Event().wait(.01)
    assert jobs.get(first["id"])["state"] == "cancelled"


def test_ollama_cancellation_interrupts_wait_for_first_token(monkeypatch):
    import http.server
    from circuit_workbench import nl_providers
    connected=threading.Event(); release=threading.Event(); cancel=threading.Event()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(b'{"models":[{"name":"local"}]}')
        def do_POST(self):
            connected.set();release.wait(3)
            try:
                self.send_response(200);self.end_headers();self.wfile.write(b'{"message":{"content":"{}"}}\n')
            except OSError: pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    monkeypatch.setattr(nl_providers,'OLLAMA',f'http://127.0.0.1:{server.server_port}')
    threading.Thread(target=server.serve_forever,daemon=True).start()
    outcome=[]
    def request():
        try: nl_providers.transport({},'test','ollama','local',cancel)
        except BaseException as e: outcome.append(e)
    worker=threading.Thread(target=request,daemon=True);worker.start()
    try:
        assert connected.wait(1);cancel.set();worker.join(.8)
        assert not worker.is_alive()
        assert isinstance(outcome[0],InterruptedError)
    finally:
        release.set();server.shutdown();server.server_close();worker.join(4)
