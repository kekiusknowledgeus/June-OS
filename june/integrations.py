from abc import ABC, abstractmethod
import asyncio
import email
from email.message import EmailMessage
import imaplib
import smtplib
import ssl
import json
from urllib.parse import quote
import httpx
from .security import Risk
from .tools import S, O


class Integration(ABC):
    @abstractmethod
    def capabilities(self): ...

    @abstractmethod
    async def execute(self, action, params): ...

    async def connect(self):
        return await self.health()

    async def disconnect(self):
        return {"status": "disconnected", "note": "Per-request connections are closed after use"}

    @abstractmethod
    async def health(self): ...


class GitHub(Integration):
    def __init__(self, vault):
        self.vault = vault

    def capabilities(self):
        return ["repositories", "issues", "pull_requests", "commits", "notifications"]

    async def health(self):
        return {"status": "ready" if self.vault.get("GITHUB_TOKEN") else "not_configured"}

    async def execute(self, action, params):
        token = self.vault.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is not configured in Windows Credential Manager")
        repo = params.get("repository", "")
        import re
        if action in {"issues", "pull_requests", "commits"} and not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise ValueError("repository must be owner/name")
        routes = {"repositories": "/user/repos", "issues": f"/repos/{repo}/issues", "pull_requests": f"/repos/{repo}/pulls", "commits": f"/repos/{repo}/commits", "notifications": "/notifications"}
        if action not in routes:
            raise ValueError("Unsupported GitHub operation")
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get("https://api.github.com" + routes[action], headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}, params={"per_page": 20})
            response.raise_for_status()
            return response.json()


class EmailIntegration(Integration):
    def __init__(self, config, vault):
        self.config, self.vault = config, vault

    def capabilities(self):
        return ["inbox", "search", "read", "draft", "send"]

    async def health(self):
        return {"status": "ready" if self.config.get("imap_host") and self.vault.get("EMAIL_PASSWORD") else "not_configured"}

    async def execute(self, action, params):
        if action == "draft":
            return {"status": "draft", "to": params["to"], "subject": params["subject"], "body": params["body"]}
        secret = self.vault.get("EMAIL_PASSWORD")
        if not secret or not self.config.get("username"):
            raise RuntimeError("Email is not configured")
        def call():
            if action == "send":
                message = EmailMessage()
                message["From"] = self.config["username"]
                message["To"] = params["to"]
                message["Subject"] = params["subject"]
                message.set_content(params["body"])
                with smtplib.SMTP_SSL(self.config["smtp_host"], self.config.get("smtp_port", 465), context=ssl.create_default_context(), timeout=20) as smtp:
                    smtp.login(self.config["username"], secret)
                    smtp.send_message(message)
                return {"status": "sent"}
            with imaplib.IMAP4_SSL(self.config["imap_host"], timeout=20) as box:
                box.login(self.config["username"], secret)
                box.select("INBOX", readonly=True)
                if action in {"inbox", "search"}:
                    if action == "search":
                        query = params.get("query", "")
                        if any(c in query for c in '\r\n"\\'):
                            raise ValueError("Invalid search text")
                        status, result = box.uid("search", None, "TEXT", '"' + query + '"')
                    else:
                        status, result = box.uid("search", None, "ALL")
                    return {"status": status, "uids": result[0].decode().split()[-30:]}
                if action == "read":
                    uid = str(params["uid"])
                    if not uid.isdigit():
                        raise ValueError("Invalid message UID")
                    status, data = box.uid("fetch", uid, "(BODY.PEEK[]<0.200000>)")
                    raw = next(d[1] for d in data if isinstance(d, tuple))
                    message = email.message_from_bytes(raw)
                    parts = [p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace") for p in message.walk() if p.get_content_type() == "text/plain"]
                    return {"from": message["From"], "subject": message["Subject"], "body": "\n".join(parts)[:20000], "trust": "untrusted email content"}
                raise ValueError("Unsupported email operation")
        return await asyncio.to_thread(call)


class CalendarIntegration(Integration):
    """CalDAV adapter with explicit event URLs and conditional writes."""
    def __init__(self, config, vault):
        self.config, self.vault = config, vault

    def capabilities(self):
        return ["list", "create", "modify"]

    async def health(self):
        return {"status": "ready" if self.config.get("url") and self.vault.get("CALENDAR_PASSWORD") else "not_configured"}

    async def execute(self, action, params):
        base = self.config.get("url", "")
        secret = self.vault.get("CALENDAR_PASSWORD")
        if not base or not secret:
            raise RuntimeError("CalDAV calendar is not configured")
        async with httpx.AsyncClient(timeout=20, auth=(self.config["username"], secret)) as client:
            if action == "list":
                body = '<?xml version="1.0"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:getetag/><c:calendar-data/></d:prop><c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"/></c:comp-filter></c:filter></c:calendar-query>'
                r = await client.request("REPORT", base, headers={"Depth": "1", "Content-Type": "application/xml"}, content=body)
            elif action in {"create", "modify"}:
                id = params["id"]
                if not id.replace("-", "").isalnum():
                    raise ValueError("Invalid event id")
                headers = {"Content-Type": "text/calendar"}
                headers["If-None-Match" if action == "create" else "If-Match"] = "*" if action == "create" else params["etag"]
                r = await client.put(base.rstrip("/") + "/" + id + ".ics", content=params["icalendar"], headers=headers)
            else:
                raise ValueError("Unsupported calendar operation")
            r.raise_for_status()
            return {"status": r.status_code, "body": r.text[:30000], "etag": r.headers.get("etag")}


class Integrations:
    def __init__(self, config, vault):
        path = config.root / "data/integrations.json"
        settings = json.loads(path.read_text()) if path.exists() else {}
        self.providers = {"github": GitHub(vault), "email": EmailIntegration(settings.get("email", {}), vault), "calendar": CalendarIntegration(settings.get("calendar", {}), vault)}

    async def health(self):
        return {k: {**await p.health(), "capabilities": p.capabilities()} for k, p in self.providers.items()}

    async def execute(self, integration, action, params):
        if integration not in self.providers:
            raise ValueError("Integration not installed")
        return await self.providers[integration].execute(action, params)

    def register(self, registry):
        registry.add("integration.execute", "Use email, CalDAV calendar or GitHub. Exact external actions require approval; credentials never enter tool arguments.", self.execute, {"integration": S, "action": S, "params": O}, ["integration", "action", "params"], Risk.EXTERNAL, external=True)
