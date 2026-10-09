"""Policy and secrets are host-owned, never controlled by model arguments."""
import hashlib
import json
import os
import re
from enum import IntEnum
from pathlib import Path
from dotenv import dotenv_values


class Risk(IntEnum):
    OBSERVE = 0
    LOCAL = 1
    MODIFY = 2
    EXTERNAL = 3
    SENSITIVE = 4
    CRITICAL = 5


class Vault:
    def __init__(self, root):
        self.path = root / ".env.local"
        self.values = {}
        self.file_keys = set()
        self.mtime = None
        self.reload()

    def reload(self):
        mtime = self.path.stat().st_mtime_ns if self.path.exists() else 0
        if mtime != self.mtime:
            for key in self.file_keys:
                self.values.pop(key, None)
            fresh = {k: v for k, v in dotenv_values(self.path).items() if v}
            self.values.update(fresh)
            self.file_keys = set(fresh)
            self.mtime = mtime

    def get(self, name):
        self.reload()
        value = os.environ.get(name) or self.values.get(name)
        if value:
            return value
        try:
            import keyring
            value = keyring.get_password("June", name)
            if value:
                self.values[name] = value
            return value
        except Exception:
            return None

    def set(self, name, value):
        import keyring
        keyring.set_password("June", name, value)
        self.values[name] = value

    def revoke(self, name):
        import keyring
        keyring.delete_password("June", name)
        self.values.pop(name, None)

    def redact(self, value):
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        secrets = list(self.values.values()) + [v for k, v in os.environ.items() if any(s in k.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))]
        for secret in secrets:
            if secret and len(secret) >= 6:
                text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED]", text)
        text = re.sub(r'(?i)(authorization|password|api_key|access_token)([\s\"\x27:=]+)[^\s,}\"\x27]+', r'\1\2[REDACTED]', text)
        return text


class Paths:
    def __init__(self, config):
        self.config = config

    def resolve(self, value):
        raw = Path(value)
        if not raw.is_absolute():
            raw = Path(self.config.allowed_roots[0]) / raw
        path = raw.resolve()
        roots = [Path(p).resolve() for p in self.config.allowed_roots + self.config.allowed_workspace_roots]
        if not any(path.is_relative_to(root) for root in roots):
            raise PermissionError("Path is outside configured project roots")
        relative_parts = path.relative_to(next(root for root in roots if path.is_relative_to(root))).parts
        protected = {".git", ".ssh", ".aws", ".codex", ".venv", ".cache", ".npmrc", ".pypirc", "credentials.json", "id_rsa", "id_ed25519"}
        if any(path.is_relative_to((self.config.root/folder).resolve()) for folder in ('data','models')):
            raise PermissionError('Private/runtime path is protected')
        if any(p.lower() in protected or p.lower().startswith(".env") for p in relative_parts) or path.suffix.lower() in {".pem", ".key", ".pfx"}:
            raise PermissionError("Private/runtime path is protected")
        if os.name == "nt" and (str(path).startswith("\\\\") or ":" in str(path)[2:]):
            raise PermissionError("UNC paths and alternate data streams are blocked")
        return path


def action_digest(tool, args):
    return hashlib.sha256(json.dumps([tool, args], sort_keys=True).encode()).hexdigest()


class Policy:
    def __init__(self, config):
        self.config = config

    def check(self, tool):
        if self.config.privacy and (tool.external or tool.sensor or tool.name in {"shell.run", "project.run", "project.open", "windows.action", "app.open", "path.open", "vision.analyze"}):
            raise PermissionError("Privacy mode blocks this capability")
        if tool.sensor == "screen" and not self.config.screen_enabled:
            raise PermissionError("Screen capture is disabled in settings")
        if tool.sensor == "camera" and not self.config.camera_enabled:
            raise PermissionError("Camera is disabled in settings")
        return tool.risk >= Risk.MODIFY
