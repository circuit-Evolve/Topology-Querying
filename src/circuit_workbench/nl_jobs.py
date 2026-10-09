"""One local search at a time, cancellable and bounded retained job history."""
from collections import OrderedDict
import copy
import threading
import time
import uuid


class SearchJobs:
    def __init__(self, execute):
        self.execute, self.lock = execute, threading.RLock()
        self.jobs = OrderedDict()

    def start(self, request):
        with self.lock:
            if any(j["state"] in {"running", "queued"} for j in self.jobs.values()):
                raise ValueError("A natural-language search is already running. Cancel it first.")
            while len(self.jobs) >= 20:
                self.jobs.popitem(last=False)
            identifier = str(uuid.uuid4())
            self.jobs[identifier] = {"id": identifier, "state": "queued", "stage": "queued", "result": None, "error": "", "cancel": threading.Event(), "created": time.time()}
            threading.Thread(target=self._run, args=(identifier, request), daemon=True, name="atlas-search").start()
            return self.get(identifier)

    def _run(self, identifier, request):
        job = self.jobs[identifier]
        with self.lock:
            job["state"] = "running"
        def progress(stage):
            if job["cancel"].is_set():
                raise InterruptedError()
            with self.lock:
                job["stage"] = stage
        try:
            result = self.execute(request, job["cancel"], progress)
            with self.lock:
                if job["cancel"].is_set():
                    job["state"] = "cancelled"
                else:
                    job.update(state="complete", stage="complete", result=result)
        except InterruptedError:
            with self.lock:
                job.update(state="cancelled", stage="cancelled")
        except Exception as exc:
            with self.lock:
                message = str(exc) if isinstance(exc, ValueError) else "Search failed. Check Neo4j and the selected provider; no dataset changes were made."
                job.update(state="failed", stage="failed", error=message)

    def get(self, identifier):
        with self.lock:
            if identifier not in self.jobs:
                raise KeyError(identifier)
            return copy.deepcopy({k: v for k, v in self.jobs[identifier].items() if k != "cancel"})

    def cancel(self, identifier):
        with self.lock:
            if identifier not in self.jobs:
                raise KeyError(identifier)
            self.jobs[identifier]["cancel"].set()
            return self.get(identifier)

    def stop(self):
        with self.lock:
            for job in self.jobs.values():
                job["cancel"].set()
