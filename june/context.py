"""Durable, source-labelled working context and relevant personal/project timeline."""
import time
from pathlib import Path
from .windows import active_window


class CurrentContext:
    transient = {"active_window", "active_application", "current_task", "pending_permission", "running_jobs"}

    def __init__(self, store, redact):
        self.store, self.redact = store, redact
        self.facts = (store.get("working", "current") or {}).get("facts", {})
        for key in self.transient:
            if key in self.facts:
                self.facts[key]["stale"] = True

    def set(self, key, value, source, confidence=1.0):
        import json
        self.facts[key] = {"value": json.loads(self.redact(json.dumps(value, default=str))), "source": source, "confidence": confidence, "observed_at": time.time(), "stale": False}
        self.persist()

    def value(self, key, default=None):
        fact = self.facts.get(key)
        return fact["value"] if fact else default

    def snapshot(self):
        return self.facts

    def persist(self):
        self.store.put("working", {"facts": self.facts}, "current")

    def project(self, query=None):
        projects = self.store.list("project")
        if query:
            needle = query.casefold().strip(" .!?")
            matches = [p for p in projects if needle in [p["id"].casefold(), p["name"].casefold(), *[a.casefold() for a in p.get("aliases", [])]]]
            return matches[0] if len(matches) == 1 else None
        return next((p for p in projects if p["id"] == self.value("current_project")), None)

    def associate_path(self, path):
        try:
            resolved = Path(path).resolve()
            matches = [p for p in self.store.list("project") if resolved.is_relative_to(Path(p["root_path"]).resolve())]
            if matches:
                project = max(matches, key=lambda p: len(p["root_path"]))
                self.set("current_project", project["id"], "observed tool path")
        except (ValueError, OSError):
            return

    def observe_desktop(self):
        try:
            window = active_window()
            # June's own windows should not replace the application that summoned her.
            if window["title"].lower().startswith("june"):
                return
            self.set("active_window", window, "Windows foreground window")
            import psutil
            try:
                process = psutil.Process(window["pid"])
                app = {"name": process.name(), "pid": process.pid}
            except psutil.Error:
                app = {"name": "unknown", "pid": window["pid"]}
            self.set("active_application", app, "Windows process")
            matches = [p for p in self.store.list("project") if any(alias.casefold() in window["title"].casefold() for alias in [p["name"], *p.get("aliases", [])])]
            if len(matches) == 1 and not (self.value('current_project') and self.facts.get('current_project',{}).get('confidence',0)>=.9):
                self.set("current_project", matches[0]["id"], "window title matched registered project", .8)
        except (OSError, RuntimeError):
            return

    def observe_tool(self, name, args, result):
        recent = self.value("recent_tool_calls", [])[-7:]
        recent.append({"tool": name, "arguments": args, "status": result["status"], "observed_at": time.time()})
        self.set("recent_tool_calls", recent, "host execution")
        if result["status"] != "success":
            self.set("recent_error", {"tool": name, "error": result.get("error")}, "tool failure")
            return
        data = result["result"]
        if name.startswith("file."):
            path = args.get("path", args.get("destination"))
            if path:
                self.associate_path(path)
                self.set("active_file", path, name)
        if name in {"shell.run", "project.run"}:
            self.set("recent_command", {"arguments": args, **data}, name)
            self.set("recent_error", {"stdout": data.get("stdout"), "stderr": data.get("stderr"), "returncode": data.get("returncode")} if data.get("returncode") else None, name)
            if args.get("cwd"):
                self.associate_path(args["cwd"])
        if name in {"screen.capture", "vision.analyze"}:
            self.set("recent_screen_observation", data, name)
        if name.startswith("browser.") and isinstance(data, dict) and data.get("url"):
            self.set("recent_webpage", {k: data[k] for k in ("url", "title", "tab") if k in data}, name)


class Timeline:
    def __init__(self, store, redact):
        self.store, self.redact = store, redact

    def add(self, type, summary, project=None, job=None, details=None, source="June", confidence=1):
        import json
        return self.store.put("timeline", {"type": type, "summary": self.redact(summary), "project": project, "job": job, "details": json.loads(self.redact(details or {})), "source": source, "confidence": confidence})

    def query(self, project=None, since=0, until=None, limit=40):
        until = until or time.time() + 1
        return [e for e in self.store.list("timeline", 3000) if (not project or e.get("project") == project) and since <= e["created_at"] <= until][:limit]
