"""Windows RegisterHotKey; no global keystroke recording or polling."""
import ctypes
from ctypes import wintypes
import threading


def parse_hotkey(spec):
    pieces = [p.strip().lower() for p in spec.split("+")]
    modifiers = {"alt": 1, "ctrl": 2, "control": 2, "shift": 4, "win": 8}
    mask = 0x4000  # MOD_NOREPEAT
    for p in pieces[:-1]:
        if p not in modifiers:
            raise ValueError("Supported hotkey modifiers: Ctrl, Alt, Shift, Win")
        mask |= modifiers[p]
    key = pieces[-1]
    if key == "space":
        code = 0x20
    elif len(key) == 1 and key.isascii() and key.isalnum():
        code = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        code = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError("Use Space, a letter/digit, or F1–F12")
    return mask, code


class GlobalHotkey:
    def __init__(self, spec, callback, status):
        self.spec, self.callback, self.status = spec, callback, status
        self.thread_id = None
        self.thread = None

    def start(self):
        modifiers, key = parse_hotkey(self.spec)
        def listen():
            user = ctypes.windll.user32
            self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            if not user.RegisterHotKey(None, 0x4A55, modifiers, key):
                self.status("unavailable: shortcut is already in use")
                return
            self.status("registered: " + self.spec)
            try:
                msg = wintypes.MSG()
                while user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312:
                        self.callback()
            finally:
                user.UnregisterHotKey(None, 0x4A55)
        self.thread = threading.Thread(target=listen, daemon=True, name="JuneHotkey")
        self.thread.start()

    def stop(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if self.thread:
            self.thread.join(timeout=2)
