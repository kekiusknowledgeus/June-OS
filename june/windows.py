import asyncio
import ctypes
from ctypes import wintypes
import os
import time
import uuid
import hashlib
from pathlib import Path
import psutil
from .security import Risk, Paths
from .tools import S, N, A


def active_application():
    """Process identity only: no title, window text, image, or document content."""
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(user.GetForegroundWindow(), ctypes.byref(pid))
    if not pid.value:
        raise RuntimeError('No foreground application')
    return {'name': psutil.Process(pid.value).name(), 'pid': pid.value, 'observed_at': time.time()}


def active_window():
    if os.name != "nt":
        raise RuntimeError("Windows desktop unavailable")
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    handle = user.GetForegroundWindow()
    title = ctypes.create_unicode_buffer(1024)
    user.GetWindowTextW(handle, title, 1024)
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    rect = wintypes.RECT()
    user.GetWindowRect(handle, ctypes.byref(rect))
    return {"title": title.value, "handle": int(handle or 0), "pid": pid.value, "rect": [rect.left, rect.top, rect.right, rect.bottom], "observed_at": time.time()}


class Windows:
    def __init__(self, config):
        self.config = config
        self.paths = Paths(config)
        self.last_capture = None
        self.pending_verification = None

    async def observe(self):
        return {"active_window": active_window(), "processes": [{"pid": p.pid, "name": p.info["name"]} for p in psutil.process_iter(["name"])][:300]}

    async def capture(self, monitor=1, active=False):
        if self.config.privacy or not self.config.screen_enabled:
            raise PermissionError("Screen capture disabled")
        import mss
        from PIL import Image
        def take():
            with mss.mss() as screen:
                target = active_window()
                if active:
                    l, t, r, b = target["rect"]
                    region = {"left": l, "top": t, "width": r-l, "height": b-t}
                else:
                    if monitor < 0 or monitor >= len(screen.monitors):
                        raise ValueError("Monitor is unavailable")
                    region = screen.monitors[monitor]
                shot = screen.grab(region)
                im = Image.frombytes("RGB", shot.size, shot.rgb)
                current = active_window()
                if active and any(current[k] != target[k] for k in ('handle', 'title', 'rect')):
                    raise ValueError('Foreground window changed during capture; capture again')
                path = self.config.root / "data/captures" / f"{uuid.uuid4().hex}.png"
                im.save(path)
                self.last_capture = {"capture_id": path.stem, "path": str(path), "width": im.width, "height": im.height, "origin": [region["left"], region["top"]], "observed_at": time.time(), "window": target, "active": active, "monitor": monitor, "image_hash": hashlib.sha256(im.tobytes()).hexdigest()}
                if self.pending_verification == 'after-capture-required':
                    self.pending_verification = str(path)
                return self.last_capture
        return await asyncio.to_thread(take)

    async def action(self, action, x=0, y=0, text="", keys=None, amount=0, expected_window="", capture_id=""):
        if self.config.privacy or not self.config.screen_enabled:
            raise PermissionError("GUI control requires screen permission")
        if self.pending_verification:
            raise ValueError("Analyze the previous action's after screenshot before another GUI action")
        observed = self.last_capture
        if not observed or observed["capture_id"] != capture_id or time.time() - observed["observed_at"] > 120:
            raise ValueError("Missing or stale capture_id; capture and inspect the screen again")
        before = await self.capture(observed["monitor"], observed["active"])
        if not expected_window or before["window"]["title"] != expected_window or any(before["window"][k] != observed["window"][k] for k in ("handle", "rect")) or before["image_hash"] != observed["image_hash"]:
            raise ValueError("Screen or target window changed; inspect the fresh capture before retrying")
        import pyautogui as pg
        pg.FAILSAFE = True
        if action == "click":
            if not (0 <= x < before["width"] and 0 <= y < before["height"]):
                raise ValueError("Coordinates outside captured monitor")
            pg.click(before["origin"][0] + x, before["origin"][1] + y)
        elif action == "type":
            if not text.isascii():
                raise ValueError('GUI typing supports ASCII only; use a structured browser or file tool for Unicode')
            pg.write(text, interval=.01)
        elif action == "hotkey":
            if not keys or any(not isinstance(key, str) or key not in pg.KEYBOARD_KEYS for key in keys):
                raise ValueError('Hotkey requires supported keyboard keys')
            pg.hotkey(*(keys or []))
        elif action == "scroll":
            pg.scroll(max(-20, min(20, amount)))
        else:
            raise ValueError("Unknown GUI action")
        # Keep the verification gate closed even if after-capture fails or the
        # task is cancelled after a real input was dispatched.
        self.pending_verification = 'after-capture-required'
        await asyncio.sleep(.3)
        after = await self.capture(observed["monitor"], observed["active"])
        self.pending_verification = after["path"]
        return {"status": "action_performed_outcome_unverified", "before": before, "after": after, "instruction": "Analyze after screenshot to verify outcome before continuing"}

    async def open(self, path):
        p = self.paths.resolve(path)
        if not p.exists():
            raise FileNotFoundError(str(p))
        os.startfile(str(p))
        return {"opened": str(p), "observed": active_window()}

    async def app(self, name):
        # Only a curated executable map; no model-provided command-line strings.
        apps = {"notepad": "notepad.exe", "calculator": "calc.exe", "explorer": "explorer.exe"}
        if name not in apps:
            raise ValueError("Application not registered: choose notepad, calculator or explorer")
        import subprocess
        p = subprocess.Popen([apps[name]])
        return {"pid": p.pid, "started": name}

    async def focus(self, title):
        import pygetwindow
        windows = pygetwindow.getWindowsWithTitle(title)
        if len(windows) != 1:
            raise ValueError("Window title must identify exactly one window")
        windows[0].activate()
        await asyncio.sleep(.1)
        observed = active_window()
        if observed['handle'] != windows[0]._hWnd:
            raise RuntimeError('Windows did not grant foreground focus; observe before retrying')
        return observed

    async def close(self, pid):
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        return {"pid": pid, "name": name, "status": "termination_requested"}

    async def clipboard(self, text=None):
        import pyperclip
        if text is not None:
            pyperclip.copy(text)
            return {"status": "written"}
        return {"text": pyperclip.paste()[:10000]}

    def register(self, r):
        r.add("windows.observe", "Observe active window and running processes", self.observe)
        r.add("screen.capture", "Capture selected monitor or active window locally", self.capture, {"monitor": N, "active": {"type": "boolean"}}, sensor="screen")
        r.add("windows.action", "GUI fallback. Requires recent capture_id and exact observed window title; refuses changed pixels/windows. Coordinates relative to that capture. Analyze returned after screenshot before next action.", self.action, {"action": S, "x": N, "y": N, "text": S, "keys": A, "amount": N, "expected_window": S, "capture_id": S}, ["action", "expected_window", "capture_id"], Risk.EXTERNAL, sensor="screen")
        r.add("path.open", "Open an allowed file/folder using Windows", self.open, {"path": S}, ["path"], Risk.MODIFY)
        r.add("app.open", "Open registered application: notepad/calculator/explorer", self.app, {"name": S}, ["name"], Risk.LOCAL)
        r.add("window.focus", "Focus exactly matching window", self.focus, {"title": S}, ["title"], Risk.MODIFY)
        r.add("process.close", "Request process termination; may lose unsaved work", self.close, {"pid": N}, ["pid"], Risk.SENSITIVE)
        r.add("clipboard.access", "Read/write clipboard; may contain sensitive content", self.clipboard, {"text": S}, risk=Risk.SENSITIVE)
