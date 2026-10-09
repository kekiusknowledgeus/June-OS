"""Native desktop controller with tray lifecycle; runtime survives window close."""
import asyncio
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import webbrowser
import httpx
import uvicorn
from .api import create_app
from .hotkey import GlobalHotkey
from .windows import active_window, active_application
from .orb import JuneOrb, monitors


def launch(runtime):
    app = create_app(runtime)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=runtime.config.port, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{runtime.config.port}"
    headers = {"Authorization": "Bearer " + app.state.token}
    root = tk.Tk()
    root.title("June — Mayank's personal AI")
    root.geometry("1000x740")
    root.configure(bg="#10151b")
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame", background="#10151b")
    style.configure("TLabel", background="#10151b", foreground="#dce4ed")
    style.configure('TButton', background='#243743', foreground='#dce4ed', bordercolor='#39515f', lightcolor='#243743', darkcolor='#243743', padding=(10, 8))
    style.map('TButton', background=[('active', '#34564a')], foreground=[('active', '#e2f4ec')])
    style.configure('TEntry', fieldbackground='#0c1720', foreground='#d5ecdf', insertcolor='#b6e6ce', bordercolor='#3a5660', lightcolor='#243743', darkcolor='#243743')
    style.configure('Presence.TLabel', background='#17212b', foreground='#c8e5dc')
    style.configure('Presence.TFrame', background='#17212b')
    events = queue.Queue()
    runtime.shutdown_handler = lambda: events.put(("exit", None))
    runtime.ui_handler = lambda view: events.put(("view", view))
    state = None
    approval_views = {}
    def request(path, body=None):
        def work():
            try:
                with httpx.Client(timeout=10) as client:
                    r = client.request("POST" if body is not None else "GET", base + "/api/" + path, json=body, headers=headers)
                    r.raise_for_status()
                    if path == "state":
                        events.put(("state", r.json()))
            except Exception as exc:
                events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()
    top = ttk.Frame(root, padding=16)
    top.pack(fill="x")
    ttk.Label(top, text="JUNE", font=("Segoe UI", 28)).pack(side="left")
    status = ttk.Label(top, text="Starting local runtime…")
    status.pack(side="left", padx=20)
    ttk.Button(top, text="Privacy mode", command=lambda: request("settings", {"privacy": not (state or {}).get("health", {}).get("privacy", False)})).pack(side="right")
    ttk.Button(top, text="Stop", command=lambda: request("stop", {})).pack(side="right", padx=6)
    ttk.Button(top, text="Dashboard", command=lambda: webbrowser.open(base + "/#" + app.state.token)).pack(side="right", padx=6)
    transcript = scrolledtext.ScrolledText(root, wrap="word", bg="#17212b", fg="#dce4ed", font=("Segoe UI", 11), relief="flat", padx=20, pady=20)
    transcript.pack(fill="both", expand=True, padx=16)
    approvals = ttk.Frame(root, padding=12)
    approvals.pack(fill="x")
    composer = ttk.Frame(root, padding=16)
    composer.pack(fill="x")
    entry = ttk.Entry(composer, font=("Segoe UI", 12))
    entry.pack(side="left", fill="x", expand=True)
    def send(event=None):
        text = entry.get().strip()
        if text:
            request("chat", {"text": text})
            entry.delete(0, "end")
    entry.bind("<Return>", send)
    ttk.Button(composer, text="Send", command=send).pack(side="left", padx=8)
    ttk.Button(composer, text="Talk", command=lambda: request("voice/talk", {})).pack(side="left")
    # The palette leaves the underlying app untouched and restores its focus on dismiss.
    overlay = tk.Toplevel(root)
    overlay.withdraw()
    overlay.title("June palette")
    overlay.attributes("-topmost", True)
    overlay.configure(bg="#17212b")
    overlay.geometry("640x330")
    palette_status = ttk.Label(overlay, text="JUNE", font=("Segoe UI", 16), style='Presence.TLabel')
    palette_status.pack(anchor="w", padx=20, pady=15)
    palette_entry = ttk.Entry(overlay, font=("Segoe UI", 14))
    palette_entry.pack(fill="x", padx=20)
    palette_context = ttk.Label(overlay, text='Connecting to June…', wraplength=580, style='Presence.TLabel')
    palette_context.pack(anchor='w', padx=20, pady=10)
    suggestions = ttk.Frame(overlay, padding=15, style='Presence.TFrame')
    suggestions.pack(fill="x")
    previous_window = None
    def dismiss():
        overlay.withdraw()
        if previous_window:
            try:
                import ctypes
                from ctypes import wintypes
                ctypes.windll.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
                ctypes.windll.user32.SetForegroundWindow(previous_window["handle"])
            except (OSError, KeyError):
                pass
    def palette_send(text=None):
        value = text or palette_entry.get().strip()
        if value:
            dismiss()
            request("chat", {"text": value})
            palette_entry.delete(0, "end")
    palette_entry.bind("<Return>", lambda _: palette_send())
    overlay.bind("<Escape>", lambda _: dismiss())
    overlay.protocol("WM_DELETE_WINDOW", dismiss)
    for label, command in [("Continue", "continue where I left off"), ("Look", "look at this"), ("Tasks", "what needs my attention"), ("Brain", "show me your brain")]:
        ttk.Button(suggestions, text=label, command=lambda c=command: palette_send(c)).pack(side="left", padx=4)
    ttk.Button(suggestions, text="Talk", command=lambda: (dismiss(), request("voice/talk", {}))).pack(side="left", padx=4)
    ttk.Button(suggestions, text='Stop', command=lambda: request('stop', {})).pack(side='left', padx=4)
    secondary = ttk.Frame(overlay, padding=15, style='Presence.TFrame')
    secondary.pack(fill='x')
    def action(name):
        if name == 'ask':
            events.put(('summon', active_window()))
        elif name == 'talk':
            dismiss()
            request('voice/talk', {})
        elif name == 'stop':
            request('stop', {})
        elif name == 'privacy':
            request('settings', {'privacy': not runtime.config.privacy})
        elif name == 'mute':
            request('settings', {'voice_enabled': False})
        elif name == 'hide':
            request('presence/preferences', {'orb_enabled': False})
        elif name == 'approval':
            pending = runtime.presence.snapshot()['pending_approval']
            if pending in approval_views:
                overlay.withdraw()
                root.deiconify()
                approval_views[pending]()
            else:
                events.put(('view', 'jobs'))
        else:
            events.put(('view', 'conversation' if name == 'dashboard' else name))
    for label, name in [('Review approval','approval'), ('Current task','jobs'), ('Mute','mute'), ('Privacy','privacy'), ('Hide orb','hide')]:
        ttk.Button(secondary, text=label, command=lambda n=name: action(n)).pack(side='left', padx=3)
    def orb_click():
        if runtime.presence.snapshot()['pending_approval']:
            action('approval')
        else:
            action('ask')
    orb = JuneOrb(root, orb_click, lambda values: request('presence/preferences', values), action)
    hotkey = GlobalHotkey(runtime.config.hotkey, lambda: events.put(("summon", active_window())), lambda s: events.put(("hotkey", s)))
    try:
        hotkey.start()
    except Exception as exc:
        events.put(("hotkey", "unavailable: " + str(exc)))
    last = ""
    last_approvals = ""
    def update():
        nonlocal state, last, last_approvals, previous_window
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "show":
                root.deiconify()
            elif kind == "summon":
                if value and value.get('handle') and value.get('pid') and value['pid'] != __import__('os').getpid():
                    previous_window = value
                    if not runtime.config.privacy:
                        try:
                            import psutil
                            runtime.foreground_app = {'name': psutil.Process(value['pid']).name(), 'pid': value['pid'], 'observed_at': value['observed_at']}
                        except psutil.Error:
                            runtime.foreground_app = None
                if value and value.get('handle') and value.get('pid') and value['pid'] != __import__('os').getpid():
                    request("context/window", value)
                import ctypes
                from ctypes import wintypes
                rect = (value or {}).get('rect', [0, 0, 640, 330])
                screen = min(monitors(), key=lambda s: abs((s[0]+s[2])/2-(rect[0]+rect[2])/2)+abs((s[1]+s[3])/2-(rect[1]+rect[3])/2))
                x = screen[0] + max(0, (screen[2]-screen[0]-640)//2)
                y = screen[1] + max(0, (screen[3]-screen[1]-330)//3)
                overlay.geometry('640x330')
                overlay.deiconify()
                overlay.lift()
                overlay.update_idletasks()
                handle = ctypes.windll.user32.GetAncestor(overlay.winfo_id(), 2)
                ctypes.windll.user32.SetWindowPos(handle, -1, x, y, 0, 0, 0x11)
                palette_entry.focus_force()
            elif kind == "view":
                webbrowser.open(base + "/?view=" + value + "#" + app.state.token)
            elif kind == "hotkey":
                runtime.hotkey_status = value
            elif kind == "exit":
                root.quit()
            elif kind == "error":
                status.config(text=value[:110])
            elif kind == "state":
                state = value
                health = state["health"]
                project = runtime.current.project()
                palette_status.config(text="JUNE · " + health["voice"] + (" · " + project["name"] if project else ""))
                status.config(text=("PRIVACY · " if health["privacy"] else "") + health["voice"] + f" · {health['active_jobs']} active")
                text = "\n\n".join(("Mayank" if m["role"] == "user" else "June") + "\n" + m["content"] for m in state["messages"])
                for job in state["jobs"]:
                    if job["status"] != "completed":
                        text += "\n\n" + job["status"].upper() + ": " + job.get("progress", job.get("error", job["request"]))
                if not text:
                    text = "June is ready.\n\nYour memory, projects, tasks and actions live here. Open Dashboard to manage settings and records.\n\nMicrophone and screen capture are disabled until you enable them."
                if text != last:
                    transcript.config(state="normal")
                    transcript.delete("1.0", "end")
                    transcript.insert("end", text)
                    transcript.config(state="disabled")
                    transcript.see("end")
                    last = text
                signature = json.dumps(state["approvals"])
                if signature != last_approvals:
                    for child in approvals.winfo_children():
                        child.destroy()
                    approval_views.clear()
                    for a in state["approvals"]:
                        def preview(item=a):
                            win = tk.Toplevel(root)
                            win.title("Approve exact action · " + item["tool"])
                            box = scrolledtext.ScrolledText(win, width=90, height=25, wrap="word")
                            box.pack(fill="both", expand=True)
                            box.insert("end", f"Risk level {item['risk']}\n{item['tool']}\n\n{item['parameters']}")
                            box.config(state="disabled")
                            choice=tk.StringVar(value='once')
                            ttk.Combobox(win,textvariable=choice,values=['once','action','app','project','folder','service'],state='readonly').pack(fill='x')
                            scope_value=ttk.Entry(win)
                            scope_value.pack(fill='x')
                            ttk.Label(win,text='For app/project/folder/service, enter its exact name or path above.').pack()
                            def decide(allow):
                                request('approve/'+item['id'],{'allow':allow,'remember':None if choice.get()=='once' else choice.get(),'scope_value':scope_value.get() or None})
                                win.destroy()
                            ttk.Button(win, text="Approve this action", command=lambda: decide(True)).pack(side="left", padx=20, pady=12)
                            ttk.Button(win, text="Deny", command=lambda: decide(False)).pack(side="right", padx=20, pady=12)
                        ttk.Button(approvals, text="Review permission: " + a["tool"], command=preview).pack(side="left")
                        approval_views[a['id']] = preview
                    last_approvals = signature
        root.after(200, update)
    last_app_check = 0
    def presence_tick():
        nonlocal last_app_check
        import time, os
        if time.monotonic() - last_app_check > 2:
            last_app_check = time.monotonic()
            if not runtime.config.privacy:
                try:
                    application = active_application()
                    if application['pid'] != os.getpid():
                        runtime.foreground_app = application
                except Exception:
                    runtime.foreground_app = None
        try:
            presence = runtime.presence.snapshot()
            orb.update(presence)
            project = presence['current_project']
            app_name = (presence.get('active_app') or {}).get('name', 'not observed')
            palette_context.config(text=f"{presence['state']} · Brain: {presence['brain_status']}\nApp: {app_name} · Project: {project['name'] if project else 'not established'}\n" + (presence.get('current_task') or 'Ready for your next request')[:170])
        except Exception:
            orb.update({**orb.snapshot, 'state': 'ERROR'})
        root.after(150, presence_tick)
    def poll():
        request("state")
        root.after(2000, poll)
    tray = None
    try:
        import pystray
        class JuneTray(pystray.Icon):
            def _on_notify(self, wparam, lparam):
                if lparam == 0x405:  # Windows NIN_BALLOONUSERCLICK
                    delivery = runtime.notifications.last_delivery or {}
                    key = delivery.get('key', '')
                    if key.startswith(('job-', 'failed-', 'approval-')):
                        events.put(('view', 'jobs&job=' + key.split('-', 1)[1]))
                    else:
                        events.put(('view', 'notification'))
                else:
                    super()._on_notify(wparam, lparam)
        from PIL import Image, ImageDraw
        icon = Image.new("RGB", (64, 64), "#17212b")
        draw = ImageDraw.Draw(icon)
        draw.ellipse((16, 16, 48, 48), fill="#b6e6ce")
        tray = JuneTray("June", icon, "June", menu=pystray.Menu(pystray.MenuItem("Open June", lambda: events.put(("show", None))), pystray.MenuItem('Show orb', lambda: request('presence/preferences', {'orb_enabled': True, 'orb_click_through': False})), pystray.MenuItem('Hide orb', lambda: request('presence/preferences', {'orb_enabled': False})), pystray.MenuItem("Mute microphone", lambda: request("settings", {"voice_enabled": False})), pystray.MenuItem("Privacy mode", lambda: request("settings", {"privacy": True})), pystray.MenuItem("Pause automation", lambda: request("settings", {"automation_paused": True})), pystray.MenuItem("Exit June", lambda: events.put(("exit", None)))))
        threading.Thread(target=tray.run, daemon=True).start()
        runtime.notifications.desktop = tray.notify
    except Exception:
        tray = None
    root.protocol("WM_DELETE_WINDOW", root.withdraw if tray else root.quit)
    root.after(500, poll)
    root.after(200, update)
    root.after(300, presence_tick)
    if runtime.config.start_minimized:
        root.withdraw()
    root.mainloop()
    orb.close()
    hotkey.stop()
    if tray:
        tray.stop()
    server.should_exit = True
    thread.join(timeout=10)
    root.destroy()
