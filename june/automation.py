import asyncio
import time
from datetime import datetime


class EventBus:
    def __init__(self, store):
        self.store = store
        self.handlers = []
        self.failures = 0

    def subscribe(self, handler):
        self.handlers.append(handler)

    async def emit(self, type, payload, importance=.5, id=None):
        event = self.store.put("event", {"type": type, "payload": payload, "importance": importance}, id)
        for handler in self.handlers:
            try:
                await handler(event)
            except Exception:
                self.failures += 1
        return event


class Notifications:
    def __init__(self, config, store):
        self.config, self.store = config, store
        self.speaker = None
        self.desktop = None
        self.last_delivery = None

    async def notify(self, title, body, key=None, urgency=.5):
        if self.config.privacy or self.config.quiet:
            return {"status": "suppressed"}
        key = key or title
        recent = self.store.list("notification", 100)
        if any(n.get("key") == key and time.time() - n["created_at"] < 120 for n in recent):
            return {"status": "cooldown"}
        item = self.store.put("notification", {"title": title, "body": body, "key": key, "urgency": urgency, "read": False})
        self.last_delivery = item
        print(f"June: {title}: {body}", flush=True)
        if self.desktop:
            try:
                self.desktop(body, title)
            except Exception:
                pass
        if self.speaker and self.config.voice_enabled:
            try:
                await self.speaker(body)
            except Exception:
                pass  # Notification remains durable even if the audio device disconnects.
        return item


class ProactiveEngine:
    def __init__(self, config, notifications):
        self.config, self.notifications = config, notifications

    async def on_event(self, event):
        if self.config.automation_paused or event["importance"] < .65:
            return
        p = event["payload"]
        await self.notifications.notify(event["type"].replace("_", " ").title(), p.get("message", p.get("title", str(p))), key=event["id"], urgency=event["importance"])


class Scheduler:
    def __init__(self, config, store, bus):
        self.config, self.store, self.bus = config, store, bus

    def schedule(self, title, due, interval=0, project=None, prompt=None):
        when = datetime.fromisoformat(due)
        if when.tzinfo is None:
            raise ValueError("Due time must include timezone offset")
        if interval and interval < 60:
            raise ValueError("Minimum repeat interval is 60 seconds")
        return self.store.put("schedule", {"title": title, "due": when.timestamp(), "interval": interval, "project": project, "enabled": True, "prompt": prompt})

    async def tick(self):
        if self.config.privacy or self.config.automation_paused:
            return
        now = time.time()
        for job in self.store.list("schedule"):
            if not job.get("enabled") or job["due"] > now:
                continue
            # Durable event ID makes a restart between delivery and acknowledgement idempotent.
            event_id = f"schedule-{job['id']}-{job['due']}"
            await self.bus.emit("scheduled_task" if job.get("prompt") else "timer", {"title": job["title"], "message": job["title"], "project": job.get("project"), "prompt": job.get("prompt")}, .8, event_id)
            interval = job.get("interval", 0)
            patch = {"enabled": False} if not interval else {"due": job["due"] + (int((now - job["due"]) // interval) + 1) * interval}
            self.store.put("schedule", patch, job["id"])
        for task in self.store.list("task"):
            if task.get("status") in {"done", "cancelled"} or not task.get("deadline") or task.get("due_notified"):
                continue
            try:
                due = datetime.fromisoformat(task["deadline"]).timestamp()
            except ValueError:
                continue
            if due <= now:
                await self.bus.emit("task_due", {"title": task["title"]}, .85, f"task-{task['id']}")
                self.store.put("task", {"due_notified": True}, task["id"])


class Watcher:
    """Opt-in polling of specific files and processes; bounded and no content upload."""
    def __init__(self, config, store, bus, paths):
        self.config, self.store, self.bus, self.paths = config, store, bus, paths

    async def tick(self):
        if self.config.privacy or self.config.automation_paused:
            return
        import psutil
        for watch in self.store.list("watch"):
            try:
                if watch["kind"] == "file":
                    p = self.paths.resolve(watch["target"])
                    state = p.stat().st_mtime_ns if p.exists() else None
                elif watch["kind"] == "process":
                    state = sorted(p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == watch["target"].lower())
                else:
                    continue
                if "state" in watch and state != watch["state"]:
                    await self.bus.emit("file_changed" if watch["kind"] == "file" else "process_changed", {"message": f"{watch['target']} changed", "observed": state}, .7)
                self.store.put("watch", {"state": state}, watch["id"])
            except (OSError, PermissionError, psutil.Error):
                continue
