"""Original vector-drawn June Presence; one small Tk window, no webview or GPU loop."""
import ctypes
from ctypes import wintypes
import math
import time
import tkinter as tk

COLORS = {'IDLE': '#a2ddc9', 'LISTENING': '#68e8db', 'THINKING': '#a99eff', 'SPEAKING': '#96eac9', 'EXECUTING': '#71b8ff', 'OBSERVING': '#82d3ed', 'WAITING FOR APPROVAL': '#ffc279', 'MUTED': '#8399a7', 'PRIVACY MODE': '#c8a8e8', 'BRAIN UNAVAILABLE': '#e2ae7b', 'ERROR': '#ff8295', 'OFFLINE': '#8198af'}


def monitors():
    rectangles = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def visit(handle, dc, rect, data):
        r = rect.contents
        rectangles.append((r.left, r.top, r.right, r.bottom))
        return True
    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_type(visit), 0)
    return rectangles or [(0, 0, 1366, 768)]


def clamp_position(x, y, size, screens):
    if x is None or y is None:
        l, t, r, b = next((s for s in screens if s[0] == 0 and s[1] == 0), screens[0])
        return r - size - 28, b - size - 70
    # Keep the full orb on the nearest attached monitor, including negative origins.
    def distance(s):
        l, t, r, b = s
        return max(l-x, 0, x-r)**2 + max(t-y, 0, y-b)**2
    l, t, r, b = min(screens, key=distance)
    return max(l, min(x, r-size)), max(t, min(y, b-size))


class JuneOrb:
    def __init__(self, root, on_click, on_save, on_action):
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title('June Presence')
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.configure(bg='#010203')
        self.window.attributes('-transparentcolor', '#010203')
        self.canvas = tk.Canvas(self.window, bg='#010203', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.on_click, self.on_save = on_click, on_save
        self.snapshot = {'state': 'OFFLINE', 'microphone_state': 'off'}
        self.prefs = {}
        self.size = 112
        self.x = self.y = 0
        self.drag = None
        self.moved = False
        self.transparent = None
        self.timer = None
        self.closed = False
        self.menu = tk.Menu(self.window, tearoff=False)
        for label, action in [('Ask June','ask'), ('Talk','talk'), ('Stop','stop'), ('Current task','jobs'), ('Show brain','brain'), ('Dashboard','dashboard'), ('Privacy mode','privacy'), ('Mute microphone','mute'), ('Hide orb','hide')]:
            self.menu.add_command(label=label, command=lambda a=action: on_action(a))
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.motion)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        self.window.update_idletasks()
        user = ctypes.windll.user32
        user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user.GetAncestor.restype = wintypes.HWND
        self.hwnd = user.GetAncestor(self.window.winfo_id(), 2)
        self.native_style(False)
        self._animate()

    def native_style(self, transparent):
        if self.transparent == transparent:
            return
        user = ctypes.windll.user32
        get = user.GetWindowLongPtrW
        put = user.SetWindowLongPtrW
        get.argtypes = [wintypes.HWND, ctypes.c_int]
        get.restype = ctypes.c_ssize_t
        put.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        put.restype = ctypes.c_ssize_t
        style = get(self.hwnd, -20) | 0x08000000 | 0x80  # no activate + tool window
        style = style | 0x20 if transparent else style & ~0x20
        put(self.hwnd, -20, style)
        self.transparent = transparent

    def place(self, x, y):
        self.x, self.y = clamp_position(x, y, self.size, monitors())
        self.window.geometry(f'{self.size}x{self.size}')
        user = ctypes.windll.user32
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.SetWindowPos(self.hwnd, -1, self.x, self.y, self.size, self.size, 0x10)  # no activation

    def update(self, snapshot):
        self.snapshot = snapshot
        prefs = snapshot.get('orb', self.prefs)
        if prefs != self.prefs:
            old = self.prefs
            self.prefs = dict(prefs)
            self.size = prefs.get('size', 112)
            self.window.attributes('-alpha', prefs.get('opacity', .92))
            if not self.drag and (not old or any(prefs.get(k) != old.get(k) for k in ('x','y','size'))):
                self.place(prefs.get('x'), prefs.get('y'))
            if prefs.get('enabled', True):
                self.window.deiconify()
                self.place(self.x, self.y)
            else:
                self.window.withdraw()
        self.native_style(bool(prefs.get('click_through')) and snapshot['state'] in {'IDLE','MUTED','OFFLINE','BRAIN UNAVAILABLE'})

    def press(self, event):
        self.drag = (event.x_root, event.y_root, self.x, self.y)
        self.moved = False

    def motion(self, event):
        if self.drag:
            x, y, px, py = self.drag
            dx, dy = event.x_root-x, event.y_root-y
            if abs(dx)+abs(dy) > 5:
                self.moved = True
                self.place(px+dx, py+dy)

    def release(self, event):
        self.drag = None
        if self.moved:
            self.on_save({'orb_x': self.x, 'orb_y': self.y})
        else:
            self.on_click()

    def _animate(self):
        if self.closed:
            return
        state = self.snapshot.get('state', 'OFFLINE')
        active = state in {'LISTENING','THINKING','SPEAKING','EXECUTING','OBSERVING','WAITING FOR APPROVAL'}
        if self.window.winfo_viewable():
            self.draw(time.monotonic(), state)
        self.timer = self.window.after(42 if active else 120, self._animate)

    def draw(self, t, state):
        c = self.canvas
        c.delete('all')
        n = self.size
        mid = n/2
        color = COLORS.get(state, '#a2ddc9')
        pulse = (math.sin(t * (5 if state == 'LISTENING' else 2))+1)/2
        radius = n*.39
        def circle(r, **kw):
            return c.create_oval(mid-r, mid-r, mid+r, mid+r, **kw)
        circle(radius, fill='#0c1822', outline='#243f4a', width=1)
        circle(radius*.86, outline=color, width=1)
        spin = t*65 if state in {'THINKING','EXECUTING','OBSERVING'} else 20
        if state == 'IDLE':
            circle(radius*(.92+.025*pulse), outline=color, width=1)
        elif state == 'MUTED':
            circle(radius*.96, outline=color, width=1, dash=(2, 5))
            c.create_line(mid-9,mid-25,mid+9,mid-12,fill=color,width=2)
        elif state == 'LISTENING':
            circle(radius*(.92+.1*pulse), outline=color, width=2)
            level = self.snapshot.get('input_level', 0)
            for i in range(16):
                angle = i*math.tau/16
                a = radius*.95
                b = a + level*n*.12*(.6+.4*math.sin(i*2))
                c.create_line(mid+a*math.cos(angle),mid+a*math.sin(angle),mid+b*math.cos(angle),mid+b*math.sin(angle),fill=color,width=2)
        elif state == 'SPEAKING':
            level = self.snapshot.get('output_level')
            if level is not None:
                amplitude = min(1, math.sqrt(level))
                circle(radius*(.9+.18*amplitude), outline=color, width=2)
                for i in range(24):
                    angle = i*math.tau/24
                    a = radius*.9
                    b = a + amplitude*n*.1
                    c.create_line(mid+a*math.cos(angle),mid+a*math.sin(angle),mid+b*math.cos(angle),mid+b*math.sin(angle),fill=color,width=2)
            else:
                # Explicit fallback: engine-state motion, no invented amplitude.
                for j in range(3):
                    circle(radius*(.7+((t*.7+j/3)%1)*.4), outline=color, width=1)
        elif state == 'WAITING FOR APPROVAL':
            circle(radius*(.95+.07*pulse), outline=color, width=3,dash=(5,4))
            c.create_text(mid,mid-n*.2,text='!',fill=color,font=('Segoe UI',max(10,n//7),'bold'))
        elif state == 'PRIVACY MODE':
            circle(radius,outline=color,width=3)
            c.create_rectangle(mid-8,mid-25,mid+8,mid-13,outline=color,width=2)
            c.create_arc(mid-6,mid-32,mid+6,mid-18,start=0,extent=180,style='arc',outline=color,width=2)
        elif state == 'ERROR':
            circle(radius*(.94+.04*pulse),outline=color,width=3)
            c.create_text(mid,mid-n*.22,text='×',fill=color,font=('Segoe UI',max(10,n//7)))
        elif state in {'OFFLINE','BRAIN UNAVAILABLE'}:
            circle(radius,outline=color,width=2,dash=(2,7) if state=='OFFLINE' else (12,5))
        else:
            if state == 'OBSERVING':
                c.create_arc(mid-radius,mid-radius,mid+radius,mid+radius,start=spin%360,extent=85,style='arc',outline=color,width=2)
            for j in range(3 if state=='THINKING' else 5):
                count = 3 if state == 'THINKING' else 5
                c.create_arc(mid-radius,mid-radius,mid+radius,mid+radius,start=(spin+j*360/count)%360,extent=40 if state=='THINKING' else 18,style='arc',outline=color,width=3)
        circle(radius*.55,fill='#112832',outline='#2d5059')
        c.create_text(mid,mid,text='JUNE',fill='#e3f5ed',font=('Segoe UI',max(8,n//10),'bold'))
        label = {'WAITING FOR APPROVAL':'APPROVAL','PRIVACY MODE':'PRIVATE','BRAIN UNAVAILABLE':'NO BRAIN'}.get(state,state)
        c.create_text(mid,n*.79,text=label,fill=color,font=('Segoe UI',max(6,n//16)))
        mic = self.snapshot.get('microphone_state') == 'active'
        c.create_oval(mid-3,n*.91-3,mid+3,n*.91+3,fill='#6be7c4' if mic else '#46555e',outline='')

    def close(self):
        self.closed = True
        if self.timer:
            self.window.after_cancel(self.timer)
        self.window.destroy()
