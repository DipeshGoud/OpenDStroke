"""Open DStroke — lightweight, open-source Windows key and mouse overlay.

Python stdlib only: tkinter + Windows low-level input hooks via ctypes.
No recording, networking, telemetry, or third-party runtime packages.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, font as tkfont
import webbrowser

APP = "Open DStroke"
VERSION = "2.1.1"
MAINTAINER = "Dipesh Goud"
REPOSITORY = "https://github.com/DipeshGoud/OpenDStroke"
TRANSPARENT = "#010203"  # transparent-color mask (never use in a key)
FONT = "Segoe UI"

PALETTES = {
    "Dark": {"bg": "#0D1420", "rail": "#111B2B", "surface": "#152132", "raised": "#1C2B40", "preview": "#0F1928", "line": "#2A3B54", "txt": "#F3F7FC", "muted": "#99AFC6", "accent": "#66DFC0", "accenttxt": "#07392E", "hover": "#273C55"},
    "Light": {"bg": "#F4F7FC", "rail": "#FFFFFF", "surface": "#FFFFFF", "raised": "#F0F4FB", "preview": "#ECF2F9", "line": "#D8E2EF", "txt": "#162338", "muted": "#697E99", "accent": "#147E69", "accenttxt": "#FFFFFF", "hover": "#E4ECF7"},
}

PRESETS = {
    "Graphite": {"fill": "#222C3A", "border": "#64748B", "text": "#FFFFFF", "shadow": "#111827", "radius": 12, "font_size": 18, "shadow_on": True},
    "Cloud": {"fill": "#F7FAFE", "border": "#C1D1E4", "text": "#1A2D48", "shadow": "#79899E", "radius": 13, "font_size": 18, "shadow_on": True},
    "Mint": {"fill": "#125D51", "border": "#73E6C4", "text": "#F0FFF8", "shadow": "#10382F", "radius": 14, "font_size": 18, "shadow_on": True},
    "Neon": {"fill": "#291D50", "border": "#9875FF", "text": "#FAF5FF", "shadow": "#141028", "radius": 12, "font_size": 18, "shadow_on": True},
    "Sunset": {"fill": "#5C2C23", "border": "#F4B273", "text": "#FFF7E9", "shadow": "#341912", "radius": 12, "font_size": 18, "shadow_on": True},
    "Ink": {"fill": "#141419", "border": "#D6D6E0", "text": "#FFFFFF", "shadow": "#09090D", "radius": 4, "font_size": 18, "shadow_on": False},
    "Lagoon": {"fill": "#123C5E", "border": "#72D9FF", "text": "#EFFCFF", "shadow": "#0A2339", "radius": 16, "font_size": 18, "shadow_on": True},
    "Rose": {"fill": "#48243D", "border": "#F79CBE", "text": "#FFF1F7", "shadow": "#291223", "radius": 16, "font_size": 18, "shadow_on": True},
}
POSITIONS = ["Bottom center", "Top center", "Bottom left", "Bottom right"]
EVENTS_LIMIT = 128


def settings_file():
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or str(Path.home())
    return Path(base) / APP / "settings.json"


def hexcolor(value, fallback):
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
            if value.lower() != TRANSPARENT:
                return value.upper()
        except ValueError:
            pass
    return fallback


def limit(value, lo, hi, fallback):
    try:
        number = float(value)
        if not (number == number and abs(number) != float("inf")):
            return fallback
        return max(lo, min(hi, number))
    except (ValueError, TypeError):
        return fallback


def normalized_style(data, original=None):
    original = original or PRESETS["Graphite"]
    if not isinstance(data, dict):
        data = {}
    return {
        **{key: hexcolor(data.get(key), original[key]) for key in ("fill", "border", "text", "shadow")},
        "radius": int(limit(data.get("radius"), 0, 22, original["radius"])),
        "font_size": int(limit(data.get("font_size"), 12, 32, original["font_size"])),
        "shadow_on": bool(data.get("shadow_on", original["shadow_on"])),
    }


def read_settings():
    try:
        path = settings_file()
        if not path.exists():
            path = path.parent.parent / "KeyHalo" / path.name
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            obj = {}
    except (OSError, ValueError, TypeError):
        obj = {}
    style = obj.get("style", "Graphite")
    return {
        "theme": obj.get("theme") if obj.get("theme") in ("Dark", "Light", "System") else "System",
        "style": style if isinstance(style, str) and (style in PRESETS or style == "Custom") else "Graphite",
        "custom": normalized_style(obj.get("custom")),
        "position": obj.get("position") if obj.get("position") in POSITIONS else "Bottom center",
        "duration": round(limit(obj.get("duration", 1.6), .5, 5, 1.6), 1),
        "opacity": int(limit(obj.get("opacity"), 20, 100, 100)),
        "keyboard": bool(obj.get("keyboard", True)),
        "mouse": bool(obj.get("mouse", True)),
        "wheel": bool(obj.get("wheel", True)),
        "cursor_ring": bool(obj.get("cursor_ring", False)),
        "click_count": bool(obj.get("click_count", True)),
    }


def write_settings(data):
    try:
        path = settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass  # In-memory settings still work if the disk is read-only.


def system_theme():
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return "Light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "Dark"
        except OSError:
            pass
    return "Dark"


def rounded(canvas, x0, y0, x1, y1, r, *, fill, outline="", width=1):
    r = max(0, min(int(r), int((x1 - x0) / 2), int((y1 - y0) / 2)))
    pts = [x0+r,y0, x1-r,y0, x1,y0, x1,y0+r, x1,y1-r, x1,y1,
           x1-r,y1, x0+r,y1, x0,y1, x0,y1-r, x0,y0+r, x0,y0]
    return canvas.create_polygon(pts, smooth=(r > 0), splinesteps=10,
                                 fill=fill, outline=outline, width=width)


def lbl(parent, title, x, y, *, color=None, size=11, bold=False, width=None, anchor="w"):
    p = parent._colors if hasattr(parent, "_colors") else None
    bg = parent.cget("bg")
    text = tk.Label(parent, text=title, bg=bg, fg=color or (p["txt"] if p else "#111"),
                    font=(FONT, size, "bold" if bold else "normal"), anchor=anchor,
                    bd=0, highlightthickness=0)
    text.place(x=x, y=y, width=width)
    return text


class UIbutton(tk.Canvas):
    """Theme-aware flat button with no extra toolkit dependencies."""
    def __init__(self, parent, title, action, *, w=130, h=40, active=False,
                 primary=False, colors=None, font_size=10):
        self.c = colors or PALETTES["Dark"]
        super().__init__(parent, width=w, height=h, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.w, self.h, self.title = w, h, title
        self.active, self.primary, self.hover = active, primary, False
        self.font_size, self.action = font_size, action
        self.bind("<Enter>", self.enter)
        self.bind("<Leave>", self.leave)
        self.bind("<Button-1>", lambda e: self.action())
        self.draw()

    def enter(self, _):
        self.hover = True
        self.draw()

    def leave(self, _):
        self.hover = False
        self.draw()

    def draw(self):
        self.delete("all")
        c = self.c
        if self.primary:
            bg = c["accent"]
            fg = c["accenttxt"]
            border = c["accent"]
        elif self.active:
            bg = c["hover"]
            fg = c["accent"] if c is PALETTES["Dark"] else c["txt"]
            border = c["accent"]
        else:
            bg = c["hover"] if self.hover else c["raised"]
            fg = c["txt"]
            border = c["line"]
        rounded(self, 1, 1, self.w-2, self.h-2, 11, fill=bg, outline=border)
        self.create_text(self.w / 2, self.h / 2, text=self.title, fill=fg,
                         font=(FONT, self.font_size, "bold"))


class WindowsInput:
    """Non-blocking keyboard/mouse hooks; forwards events to UI, never records input."""
    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14
    WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
    WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN = 0x201, 0x204, 0x207
    WM_MOUSEWHEEL, WM_XBUTTONDOWN, WM_MOUSEHWHEEL = 0x20A, 0x20B, 0x20E
    MODS = {0x10:"Shift", 0xA0:"Shift", 0xA1:"Shift", 0x11:"Ctrl", 0xA2:"Ctrl", 0xA3:"Ctrl",
            0x12:"Alt", 0xA4:"Alt", 0xA5:"Alt", 0x5B:"Win", 0x5C:"Win"}
    SPECIAL = {0x08:"Backspace",0x09:"Tab",0x0D:"Enter",0x14:"Caps",0x1B:"Esc",0x20:"Space",
               0x21:"PgUp",0x22:"PgDn",0x23:"End",0x24:"Home",0x25:"Left",0x26:"Up",
               0x27:"Right",0x28:"Down",0x2C:"PrtSc",0x2D:"Insert",0x2E:"Delete",
               0x5D:"Menu",0x90:"Num Lock",0x91:"Scroll Lock",0x6A:"Num *",0x6B:"Num +",
               0x6D:"Num -",0x6E:"Num .",0x6F:"Num /"}

    def __init__(self, events):
        self.events = events
        self.held = set()
        self.running = False
        self.thread = None
        self.thread_id = 0
        self.hooks = []
        self.callbacks = []
        self.last_click = None
        self.click_interval = .5
        self.click_distance = (2, 2)
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            self.click_interval = user32.GetDoubleClickTime() / 1000
            self.click_distance = tuple(max(1, user32.GetSystemMetrics(i) // 2) for i in (36, 37))

    @classmethod
    def keyname(cls, vk, sc=0, flags=0):
        if vk in cls.MODS:
            return cls.MODS[vk]
        if vk in cls.SPECIAL:
            return cls.SPECIAL[vk]
        if 0x30 <= vk <= 0x5A and (vk <= 0x39 or vk >= 0x41):
            return chr(vk)
        if 0x70 <= vk <= 0x87:
            return f"F{vk-0x6F}"
        if 0x60 <= vk <= 0x69:
            return f"Num {vk-0x60}"
        if sys.platform == "win32":
            try:
                value = ctypes.create_unicode_buffer(40)
                encoded = (sc << 16) | ((flags & 1) << 24)
                if ctypes.windll.user32.GetKeyNameTextW(encoded, value, len(value)):
                    return value.value[:18]
            except (OSError, AttributeError):
                pass
        return f"Key {vk}"

    def emit(self, value):
        try:
            self.events.put_nowait(value)
        except queue.Full:
            pass

    def on_key(self, vk, scan=0, flags=0, down=True):
        # Keystrokes never leave memory or reach a file.
        if not down:
            self.held.discard(vk)
            return
        if vk in self.held:
            return  # key-repeat suppression
        self.held.add(vk)
        mods = [label for label in ("Ctrl", "Shift", "Alt", "Win")
                if label in {self.MODS[v] for v in self.held if v in self.MODS}]
        if "Ctrl" in mods and "Shift" in mods and vk == 0x4F:
            self.emit(("toggle",))
            return
        if "Ctrl" in mods and "Shift" in mods and vk == 0x4B:
            self.emit(("dashboard",))
            return
        name = self.keyname(vk, scan, flags)
        keys = mods if vk in self.MODS else mods + [name]
        self.emit(("keyboard", keys[:6]))

    def on_mouse(self, message, data=0, x=0, y=0):
        names = {self.WM_LBUTTONDOWN:"Left click", self.WM_RBUTTONDOWN:"Right click",
                 self.WM_MBUTTONDOWN:"Middle click"}
        name = names.get(message)
        if message == self.WM_XBUTTONDOWN:
            name = "Mouse 4" if ((data >> 16) & 0xFFFF) == 1 else "Mouse 5"
        if name:
            now = time.monotonic()
            count = 1
            if self.last_click:
                old_name, old_x, old_y, old_time, old_count = self.last_click
                dx, dy = self.click_distance
                if (name == old_name and now - old_time <= self.click_interval
                        and abs(x - old_x) <= dx and abs(y - old_y) <= dy):
                    count = old_count + 1
            self.last_click = name, x, y, now, count
            self.emit(("mouse", name, x, y, count))
        elif message in (self.WM_MOUSEWHEEL, self.WM_MOUSEHWHEEL):
            self.last_click = None
            wheel = ctypes.c_short((data >> 16) & 0xFFFF).value
            if wheel:
                directions = ("up", "down") if message == self.WM_MOUSEWHEEL else ("right", "left")
                self.emit(("wheel", f"Scroll {directions[wheel < 0]}", x, y))

    def start(self):
        if sys.platform != "win32":
            self.emit(("error", "Global keys and clicks require Windows 10 or 11."))
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="OpenDStrokeInputHooks", daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread_id and sys.platform == "win32":
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x12, 0, 0)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)

    def _run(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        LRESULT = ctypes.c_ssize_t
        ULONG_PTR = ctypes.c_size_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        class KBD(ctypes.Structure):
            _fields_ = [("vkCode",wintypes.DWORD), ("scanCode",wintypes.DWORD),
                        ("flags",wintypes.DWORD), ("time",wintypes.DWORD), ("extra",ULONG_PTR)]
        class MOUSE(ctypes.Structure):
            _fields_ = [("point",wintypes.POINT), ("mouseData",wintypes.DWORD),
                        ("flags",wintypes.DWORD), ("time",wintypes.DWORD), ("extra",ULONG_PTR)]
        HHOOK = wintypes.HANDLE
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = HHOOK
        user32.CallNextHookEx.argtypes = [HHOOK,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.UnhookWindowsHookEx.argtypes = [HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = LRESULT
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        # Own message queue exists before stop() can send WM_QUIT.
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
        dummy = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(dummy),None,0,0,0)
        self.thread_id = kernel32.GetCurrentThreadId()

        def key_proc(ncode, wparam, lparam):
            if ncode >= 0 and self.running:
                try:
                    item = ctypes.cast(lparam,ctypes.POINTER(KBD)).contents
                    if wparam in (self.WM_KEYDOWN,self.WM_SYSKEYDOWN,self.WM_KEYUP,self.WM_SYSKEYUP):
                        self.on_key(item.vkCode,item.scanCode,item.flags,
                                    wparam in (self.WM_KEYDOWN,self.WM_SYSKEYDOWN))
                except Exception:
                    pass
            return user32.CallNextHookEx(None,ncode,wparam,lparam)

        def mouse_proc(ncode, wparam, lparam):
            # Ignore mouse movement immediately; no continuous tracking/polling.
            if ncode >= 0 and self.running and wparam in (
                    self.WM_LBUTTONDOWN,self.WM_RBUTTONDOWN,self.WM_MBUTTONDOWN,
                    self.WM_MOUSEWHEEL,self.WM_MOUSEHWHEEL,self.WM_XBUTTONDOWN):
                try:
                    item = ctypes.cast(lparam,ctypes.POINTER(MOUSE)).contents
                    self.on_mouse(wparam,item.mouseData,item.point.x,item.point.y)
                except Exception:
                    pass
            return user32.CallNextHookEx(None,ncode,wparam,lparam)

        self.callbacks = [HOOKPROC(key_proc),HOOKPROC(mouse_proc)]  # prevent GC
        module = kernel32.GetModuleHandleW(None)
        try:
            for kind, callback in ((self.WH_KEYBOARD_LL,self.callbacks[0]),
                                   (self.WH_MOUSE_LL,self.callbacks[1])):
                hook = user32.SetWindowsHookExW(kind, callback, module, 0)
                if not hook:
                    self.emit(("error",f"Windows input hook {kind} failed (error {ctypes.get_last_error()})."))
                    return
                self.hooks.append(hook)
            msg = wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg),None,0,0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:
            self.emit(("error",f"Input hook error: {exc}"))
        finally:
            for hook in self.hooks:
                user32.UnhookWindowsHookEx(hook)
            self.hooks.clear()
            self.callbacks.clear()
            self.thread_id = 0
            self.running = False


class KeyOverlay:
    """Transparent keycaps, without any rectangle behind them."""
    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=TRANSPARENT)
        self.win.wm_attributes("-topmost",True)
        if sys.platform == "win32":
            self.win.wm_attributes("-transparentcolor",TRANSPARENT)
        self.canvas = tk.Canvas(self.win,width=150,height=90,bg=TRANSPARENT,
                                highlightthickness=0,bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>",self._down)
        self.canvas.bind("<B1-Motion>",self._move)
        self.canvas.bind("<Button-3>",self._context)
        self.position = None
        self.anchor = None
        self.rows = {"keyboard": [], "mouse": []}
        self.timers = {}
        self.w,self.h = 150,88
        self.menu = tk.Menu(self.win,tearoff=0)
        self.menu.add_command(label=f"Open {APP}  (Ctrl+Shift+K)",command=app.show_dashboard)
        self.menu.add_command(label="Pause / resume  (Ctrl+Shift+O)",command=app.toggle)
        self.menu.add_command(label="Overlay options",command=lambda: app.open_page("Overlay"))
        self.menu.add_separator()
        self.menu.add_command(label="Exit",command=app.close)

    def _down(self,e):
        self.anchor = (e.x_root,e.y_root)

    def _move(self,e):
        if self.anchor is None:
            return
        if self.position is None:
            self.position = (self.win.winfo_x(),self.win.winfo_y())
        self.position = (self.position[0]+e.x_root-self.anchor[0],
                         self.position[1]+e.y_root-self.anchor[1])
        self.anchor = (e.x_root,e.y_root)
        self.draw()

    def _context(self,e):
        try:
            self.menu.tk_popup(e.x_root,e.y_root)
        finally:
            self.menu.grab_release()

    def hide(self):
        for timer in self.timers.values():
            self.win.after_cancel(timer)
        self.timers.clear()
        for kind in self.rows:
            self.rows[kind] = []
        self.win.withdraw()

    def placement(self):
        self.position = None
        self.draw()

    def clear_row(self, kind):
        timer = self.timers.pop(kind, None)
        if timer:
            self.win.after_cancel(timer)
        self.rows[kind] = []
        self.draw()

    def show(self, keys, kind="keyboard"):
        if not self.app.enabled or not keys:
            return
        self.rows[kind] = list(keys[:6])
        if kind in self.timers:
            self.win.after_cancel(self.timers[kind])
        self.timers[kind] = self.win.after(
            int(self.app.cfg["duration"] * 1000), lambda: self.clear_row(kind))
        self.draw()

    def draw(self):
        if not any(self.rows.values()):
            self.win.withdraw()
            return
        cfg = self.app.cfg
        style = self.app.style()
        font = tkfont.Font(family=FONT, size=style["font_size"], weight="bold")
        row_height = font.metrics("linespace") + 24
        widths = {kind: [max(44, font.measure(key) + 24) for key in keys]
                  for kind, keys in self.rows.items()}
        content_width = max(sum(row) + 10 * max(0, len(row) - 1) for row in widths.values())
        self.w = content_width + 16
        separate = (cfg["keyboard"] or self.rows["keyboard"]) and (
            cfg["mouse"] or cfg["wheel"] or self.rows["mouse"])
        self.h = (row_height + 10) * (2 if separate else 1) + 10
        self.canvas.configure(width=self.w,height=self.h)
        self.canvas.delete("all")
        for kind, keys in self.rows.items():
            if not keys:
                continue
            mouse = kind == "mouse"
            y = 5 + (row_height + 10 if mouse and separate else 0)
            x = 7
            border = "#43BDE7" if mouse else style["border"]
            for name, width in zip(keys, widths[kind]):
                if style["shadow_on"]:
                    rounded(self.canvas, x+2, y+4, x+width+2, y+row_height+4,
                            style["radius"], fill=style["shadow"])
                rounded(self.canvas, x, y, x+width, y+row_height, style["radius"],
                        fill=style["fill"], outline=border, width=2)
                self.canvas.create_text(x+width/2, y+row_height/2, text=name,
                                        fill=style["text"], font=font)
                x += width + 10
        if self.position is not None:
            left, top = self.position
        else:
            sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            pos = cfg["position"]
            left = max(12,(sw-self.w)//2)
            top = sh-self.h-105
            if pos == "Top center": top = 65
            if pos == "Bottom left": left = 45
            if pos == "Bottom right": left = sw-self.w-45
        self.win.geometry(f"{self.w}x{self.h}+{max(0, int(left))}+{max(0, int(top))}")
        self.win.wm_attributes("-alpha", cfg["opacity"] / 100)
        if self.win.state() == "withdrawn":
            self.win.deiconify()
            self.win.lift()

    def close(self):
        self.hide()
        self.win.destroy()


class ClickRing:
    """Short-lived optional mouse ring, not a continuous pointer tracker."""
    def __init__(self,root):
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=TRANSPARENT)
        self.win.wm_attributes("-topmost",True)
        if sys.platform == "win32":
            self.win.wm_attributes("-transparentcolor",TRANSPARENT)
        self.view = tk.Canvas(self.win,width=54,height=54,bg=TRANSPARENT,bd=0,highlightthickness=0)
        self.view.pack()
        self.timer = None
        if sys.platform == "win32":
            self.win.update_idletasks()
            try:
                usr = ctypes.windll.user32
                usr.GetParent.argtypes = [wintypes.HWND]
                usr.GetParent.restype = wintypes.HWND
                hwnd = usr.GetParent(self.win.winfo_id()) or self.win.winfo_id()
                # The ring must not intercept mouse clicks.
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT,WS_EX_LAYERED,WS_EX_TOOLWINDOW,WS_EX_NOACTIVATE = 0x20,0x80000,0x80,0x08000000
                if ctypes.sizeof(ctypes.c_void_p) == 8:
                    usr.GetWindowLongPtrW.argtypes = [wintypes.HWND,ctypes.c_int]
                    usr.GetWindowLongPtrW.restype = ctypes.c_ssize_t
                    usr.SetWindowLongPtrW.argtypes = [wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t]
                    old = usr.GetWindowLongPtrW(hwnd,GWL_EXSTYLE)
                    usr.SetWindowLongPtrW(hwnd,GWL_EXSTYLE,old | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
                else:
                    old = usr.GetWindowLongW(hwnd,GWL_EXSTYLE)
                    usr.SetWindowLongW(hwnd,GWL_EXSTYLE,old | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            except Exception:
                pass  # Optional visual enhancement only.

    def show(self,x,y,color):
        self.view.delete("all")
        self.view.create_oval(4,4,50,50,outline=color,width=4)
        self.view.create_oval(16,16,38,38,outline=color,width=2)
        self.win.geometry(f"54x54+{max(0,x-27)}+{max(0,y-27)}")
        self.win.deiconify()
        if self.timer:
            self.win.after_cancel(self.timer)
        self.timer = self.win.after(380,self.hide)

    def hide(self):
        if self.timer:
            self.win.after_cancel(self.timer)
            self.timer = None
        self.win.withdraw()

    def close(self):
        self.hide()
        self.win.destroy()


class OpenDStrokeApp:
    def __init__(self):
        self.cfg = read_settings()
        self.theme = self.cfg["theme"] if self.cfg["theme"] != "System" else system_theme()
        self.colors = PALETTES[self.theme]
        self.page = "Dashboard"
        self.enabled = True
        self.root = tk.Tk()
        self.root.title(APP)
        self.root.geometry("990x654")
        self.root.minsize(990,654)
        self.root.maxsize(990,654)
        self.root.protocol("WM_DELETE_WINDOW",self.close)
        try:
            icon = Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))/"OpenDStroke.ico"
            if icon.exists(): self.root.iconbitmap(str(icon))
        except (OSError,tk.TclError):
            pass
        self.messages = queue.Queue(maxsize=EVENTS_LIMIT)
        self._save_job = None
        self.overlay = KeyOverlay(self)
        self.click_ring = ClickRing(self.root)
        self.render_shell()
        self.input = WindowsInput(self.messages)
        self.input.start()
        self.root.after(35,self.poll)

    def persist(self):
        # Debounce slider edits; no repeated disk writes while dragging.
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(350, self.flush_settings)

    def flush_settings(self):
        self._save_job = None
        write_settings(self.cfg)

    def update_theme(self,value):
        self.cfg["theme"] = value
        self.theme = system_theme() if value == "System" else value
        self.colors = PALETTES[self.theme]
        self.persist()
        self.render_shell()

    def style(self):
        return self.cfg["custom"] if self.cfg["style"] == "Custom" else PRESETS[self.cfg["style"]]

    def pane(self,parent,x,y,w,h,*,bg=None):
        c = self.colors
        frame = tk.Frame(parent,bg=bg or c["surface"],highlightbackground=c["line"],highlightthickness=1,bd=0)
        frame.place(x=x,y=y,width=w,height=h)
        frame._colors = c
        return frame

    def button(self,parent,title,action,x,y,w=140,h=39,*,active=False,primary=False,font_size=10):
        b = UIbutton(parent,title,action,w=w,h=h,active=active,primary=primary,
                     colors=self.colors,font_size=font_size)
        b.place(x=x,y=y)
        return b

    def label(self,parent,title,x,y,*,muted=False,size=11,bold=False,width=None):
        return lbl(parent,title,x,y,color=self.colors["muted" if muted else "txt"],
                   size=size,bold=bold,width=width)

    def render_shell(self):
        for child in self.root.winfo_children():
            if child not in (self.overlay.win,self.click_ring.win):
                child.destroy()
        c = self.colors
        self.root.configure(bg=c["bg"])
        rail = tk.Frame(self.root,bg=c["rail"],highlightbackground=c["line"],highlightthickness=1)
        rail.place(x=0,y=0,width=209,height=654)
        brand = tk.Canvas(rail,width=42,height=42,bg=c["rail"],bd=0,highlightthickness=0)
        brand.place(x=20,y=24)
        rounded(brand,0,0,42,42,13,fill=c["accent"])
        brand.create_text(21,21,text="D",fill=c["accenttxt"],font=(FONT,23,"bold"))
        self.label(rail,APP,71,25,size=13,bold=True)
        self.label(rail,"Input overlay",72,49,size=9,muted=True)
        for i,(item,symbol) in enumerate((("Dashboard","▦"),("Styles","◇"),("Inputs","⌨"),("Overlay","◫"),("Settings","⚙"),("About","ⓘ"))):
            self.button(rail,f"{symbol}    {item}",lambda n=item:self.navigate(n),16,114+i*51,176,43,
                        active=self.page==item)
        self.button(rail,"Exit Open DStroke",self.close,16,535,176,38)
        self.label(rail,f"v{VERSION}  ·  MIT License",19,606,size=9,muted=True)
        main = tk.Frame(self.root,bg=c["bg"])
        main.place(x=209,y=0,width=781,height=654)
        self.main=main
        self.label(main,self.page,26,24,size=23,bold=True)
        self.button(main,"●  Live" if self.enabled else "○  Paused",self.toggle,507,24,116,37,
                    primary=self.enabled)
        self.button(main,"Hide dashboard",self.hide_dashboard,631,24,119,37)
        self.body = tk.Frame(main,bg=c["bg"])
        self.body.place(x=0,y=105,width=781,height=549)
        self.render_page()

    def navigate(self,name):
        self.page=name
        self.render_shell()

    def open_page(self, name):
        self.navigate(name)
        self.show_dashboard()

    def render_page(self):
        for w in self.body.winfo_children():w.destroy()
        getattr(self,f"page_{self.page.lower()}")()

    def preview(self,parent,x,y,w,h,*,keys=None,custom=False,mouse=False):
        style = self.cfg["custom"] if custom else self.style()
        c = self.colors
        keys = keys or ["Ctrl","Shift","S"]
        box = tk.Canvas(parent,width=w,height=h,bg=c["preview"],bd=0,highlightthickness=0)
        box.place(x=x,y=y)
        rounded(box,2,2,w-3,h-3,16,fill=c["preview"],outline=c["line"])
        fsize = min(15,style["font_size"])
        f=tkfont.Font(family=FONT,size=fsize,weight="bold")
        widths=[max(52,f.measure(item)+22) for item in keys]
        spacing=10
        total=sum(widths)+spacing*(len(widths)-1)
        cur=(w-total)/2
        top=(h-52)/2 - (26 if mouse else 0)
        for key,width in zip(keys,widths):
            if style["shadow_on"]:
                rounded(box,cur+2,top+4,cur+width+2,top+55,style["radius"],fill=style["shadow"])
            rounded(box,cur,top,cur+width,top+50,style["radius"],fill=style["fill"],
                    outline=style["border"],width=2)
            box.create_text(cur+width/2,top+25,text=key,font=f,fill=style["text"])
            cur+=width+spacing
        box._preview_keys = list(keys)
        box._preview_custom = custom
        if mouse:
            width = f.measure("Left click ×2") + 28
            x0 = (w-width)/2
            top += 61
            rounded(box,x0,top,x0+width,top+42,style["radius"],fill=style["fill"],
                    outline="#43BDE7",width=2)
            box.create_text(w/2,top+21,text="Left click ×2",font=f,fill=style["text"])
        return box

    def redraw_preview_canvas(self, canvas):
        # Refresh an existing preview in place; do not destroy a slider mid-drag.
        keys = canvas._preview_keys
        custom = canvas._preview_custom
        parent = canvas.master
        info = canvas.place_info()
        x, y = int(info["x"]), int(info["y"])
        w, h = int(canvas.cget("width")), int(canvas.cget("height"))
        canvas.destroy()
        fresh = self.preview(parent, x, y, w, h, keys=keys, custom=custom)
        if hasattr(self, "style_preview") and self.style_preview == canvas:
            self.style_preview = fresh

    def page_dashboard(self):
        b=self.body
        hero=self.pane(b,25,5,727,113)
        self.label(hero,"Overlay is running" if self.enabled else "Overlay paused",21,18,size=17,bold=True)
        self.label(hero,"Keyboard appears above mouse clicks and scrolling.",22,51,size=10,muted=True)
        self.button(hero,"Pause overlay" if self.enabled else "Start overlay",self.toggle,548,34,154,42,
                    primary=not self.enabled)
        preview=self.pane(b,25,134,448,257)
        self.label(preview,"LIVE PREVIEW",17,16,size=10,bold=True,muted=True)
        self.preview(preview,15,48,416,159,mouse=True)
        self.button(preview,"Test both rows",self.test_overlay,18,215,150,34)
        quick=self.pane(b,487,134,265,257)
        self.label(quick,"QUICK SETTINGS",17,18,size=10,bold=True,muted=True)
        self.label(quick,"Style",18,58,size=11,bold=True)
        self.label(quick,self.cfg["style"],157,60,size=10,muted=True)
        self.label(quick,"Position",18,101,size=11,bold=True)
        self.label(quick,self.cfg["position"],140,103,size=9,muted=True)
        self.label(quick,"Keyboard",18,143,size=11,bold=True)
        self.label(quick,"On" if self.cfg["keyboard"] else "Off",192,145,size=10,muted=True)
        self.label(quick,"Mouse clicks",18,183,size=11,bold=True)
        self.label(quick,"On" if self.cfg["mouse"] else "Off",192,184,size=10,muted=True)
        self.button(quick,"Edit appearance",lambda:self.navigate("Styles"),17,211,228,35)
        self.label(b,"STYLE PRESETS",27,412,size=10,bold=True,muted=True)
        for i,name in enumerate(("Graphite","Cloud","Mint","Neon")):
            self.preset_card(b,name,25+i*184,442,176,84)

    def preset_card(self,parent,name,x,y,w,h):
        style=PRESETS[name]
        f=self.pane(parent,x,y,w,h,bg=self.colors["surface"])
        sample=tk.Canvas(f,width=56,height=47,bg=self.colors["surface"],bd=0,highlightthickness=0)
        sample.place(x=7,y=16)
        rounded(sample,4,5,51,45,style["radius"],fill=style["fill"],outline=style["border"],width=2)
        sample.create_text(27,24,text="K",fill=style["text"],font=(FONT,14,"bold"))
        self.label(f,name,66,15 if h < 77 else 22,size=11,bold=True)
        if self.cfg["style"] == name:
            self.label(f,"Selected",66,37 if h < 77 else 48,size=9,muted=True)
        sample.place_configure(y=(h-47)//2)
        for child in (f,sample):
            child.configure(cursor="hand2")
            child.bind("<Button-1>",lambda e,n=name:self.set_style(n))
        for child in f.winfo_children():
            child.bind("<Button-1>",lambda e,n=name:self.set_style(n))

    def page_styles(self):
        b=self.body
        self.label(b,"Choose a preset or design your own keycaps.",27,4,size=11,muted=True)
        for i,name in enumerate(PRESETS):
            self.preset_card(b,name,25+(i%4)*184,35+(i//4)*65,176,57)
        editor=self.pane(b,25,171,436,376)
        self.label(editor,"CUSTOM STYLE",18,16,size=10,bold=True,muted=True)
        self.label(editor,"Colors",18,50,size=13,bold=True)
        labels=[("fill","Key background"),("border","Border color"),("text","Key text"),("shadow","Shadow color")]
        for i,(key,display) in enumerate(labels):
            y=84+i*42
            self.label(editor,display,20,y+5,size=10)
            swatch=tk.Canvas(editor,width=40,height=28,bg=editor.cget("bg"),highlightthickness=0,bd=0,cursor="hand2")
            swatch.place(x=219,y=y)
            rounded(swatch,2,2,38,26,7,fill=self.cfg["custom"][key],outline=self.colors["line"])
            swatch.bind("<Button-1>",lambda event,k=key:self.pick_color(k))
            self.button(editor,"Choose",lambda k=key:self.pick_color(k),273,y-3,128,34)
        self.label(editor,"Font size",20,262,size=10)
        self.label(editor,"Corner radius",20,303,size=10)
        self.slider(editor,"font_size",220,260,12,32)
        self.slider(editor,"radius",220,303,0,22)
        self.button(editor,"Save style",self.export_custom,15,341,130,30)
        self.button(editor,"Import style",self.import_custom,157,341,130,30)
        self.button(editor,"Use custom",lambda:self.set_style("Custom"),298,341,121,30,primary=True)
        aside=self.pane(b,476,171,276,376)
        self.label(aside,"YOUR PREVIEW",18,17,size=10,bold=True,muted=True)
        self.style_preview = self.preview(aside,12,52,250,158,keys=["Ctrl","Alt"],custom=True)
        self.label(aside,"Custom style",17,229,size=13,bold=True)
        self.label(aside,"Change colors to edit your design.",17,258,size=9,muted=True)
        self.label(aside,"Shadow",17,300,size=10,bold=True)
        self.button(aside,"On" if self.cfg["custom"]["shadow_on"] else "Off",
                    self.toggle_shadow,131,289,125,34,
                    active=self.cfg["custom"]["shadow_on"])
        self.label(aside,"Export and share your preset as JSON.",17,339,size=9,muted=True)

    def slider(self,parent,field,x,y,lo,hi):
        c=self.colors
        current=int(self.cfg["custom"][field])
        var=tk.IntVar(value=current)
        val=self.label(parent,str(current),362,y+3,size=10,bold=True)
        s=tk.Scale(parent,from_=lo,to=hi,orient="horizontal",resolution=1,variable=var,
                   showvalue=False,bd=0,highlightthickness=0,sliderlength=14,
                   bg=parent.cget("bg"),fg=c["txt"],activebackground=c["accent"],
                   troughcolor=c["raised"],width=11,length=140)
        s.place(x=x,y=y-6)
        def update(v):
            self.cfg["custom"][field]=int(float(v))
            val.configure(text=str(int(float(v))))
            self.cfg["style"]="Custom"
            self.persist()
            if hasattr(self, "style_preview") and self.style_preview.winfo_exists():
                self.redraw_preview_canvas(self.style_preview)
            self.overlay.draw()
        s.configure(command=update)

    def refresh_preview(self):
        # Rebuild only the current content, not the whole app/overlay.
        self.render_page()
        self.overlay.draw()

    def toggle_shadow(self):
        self.cfg["custom"]["shadow_on"] = not self.cfg["custom"]["shadow_on"]
        self.cfg["style"] = "Custom"
        self.persist()
        self.refresh_preview()

    def pick_color(self,key):
        initial=self.cfg["custom"][key]
        result=colorchooser.askcolor(color=initial,parent=self.root,title=f"{APP} — {key}")[1]
        if result:
            self.cfg["custom"][key]=hexcolor(result,initial)
            self.cfg["style"]="Custom"
            self.persist()
            self.refresh_preview()

    def set_style(self,name):
        self.cfg["style"]=name
        self.persist()
        self.render_page()
        self.overlay.draw()

    def export_custom(self):
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension=".json",
                                         initialfile="OpenDStroke_style.json",filetypes=[("JSON preset","*.json")])
        if path:
            try:Path(path).write_text(json.dumps(self.cfg["custom"],indent=2),encoding="utf-8")
            except OSError as exc:messagebox.showerror("Save failed",str(exc),parent=self.root)

    def import_custom(self):
        path=filedialog.askopenfilename(parent=self.root,filetypes=[("JSON preset","*.json")])
        if path:
            try:
                item=json.loads(Path(path).read_text(encoding="utf-8"))
                if not isinstance(item,dict):raise ValueError("Expected a style JSON object.")
                self.cfg["custom"]=normalized_style(item)
                self.set_style("Custom")
            except (OSError,ValueError) as exc:messagebox.showerror("Import failed",str(exc),parent=self.root)

    def switch(self,parent,title,detail,key,y):
        self.label(parent,title,18,y,size=12,bold=True)
        self.label(parent,detail,19,y+25,size=9,muted=True)
        v=self.cfg[key]
        self.button(parent,"On" if v else "Off",lambda k=key:self.flip(k),565,y+3,120,37,active=v)

    def flip(self,key):
        self.cfg[key]=not self.cfg[key]
        if key == "keyboard" and not self.cfg[key]:
            self.overlay.clear_row("keyboard")
        if key in ("mouse", "wheel") and not self.cfg[key]:
            self.overlay.clear_row("mouse")
        if key == "cursor_ring" and not self.cfg[key]:
            self.click_ring.hide()
        self.overlay.draw()
        self.persist()
        self.render_page()

    def page_inputs(self):
        b=self.body
        self.label(b,"Choose what appears on the overlay.",27,4,size=11,muted=True)
        panel=self.pane(b,25,40,727,397)
        self.switch(panel,"Keyboard shortcuts","Show pressed keys and combinations such as Ctrl + C.","keyboard",24)
        self.switch(panel,"Mouse clicks","Show left, right, middle and extra mouse-button clicks.","mouse",100)
        self.switch(panel,"Mouse wheel","Show vertical and horizontal scrolling.","wheel",176)
        self.switch(panel,"Cursor ring on click","Briefly highlight the pointer when you click.","cursor_ring",252)
        self.switch(panel,"Show click count","Group rapid clicks of the same button and display the count.","click_count",328)

    def page_overlay(self):
        b=self.body
        self.label(b,"Keep your teaching screen clear and readable.",27,4,size=11,muted=True)
        top=self.pane(b,25,39,727,169)
        self.label(top,"OVERLAY POSITION",18,18,size=10,bold=True,muted=True)
        for i,name in enumerate(POSITIONS):
            x=18+(i%2)*350
            y=52+(i//2)*51
            self.button(top,name,lambda n=name:self.change_position(n),x,y,335,45,
                        active=self.cfg["position"]==name)
        bottom=self.pane(b,25,223,727,248)
        self.label(bottom,"DISPLAY DURATION",18,17,size=10,bold=True,muted=True)
        self.duration_label=self.label(bottom,f"{self.cfg['duration']:.1f} seconds",533,17,size=10,bold=True)
        slider=tk.Scale(bottom,from_=0.5,to=5.0,orient="horizontal",resolution=.1,
                        bd=0,highlightthickness=0,showvalue=False,
                        bg=bottom.cget("bg"),troughcolor=self.colors["raised"],
                        activebackground=self.colors["accent"],sliderlength=18,length=655,
                        command=self.set_duration)
        slider.set(self.cfg["duration"])
        slider.place(x=19,y=50)
        self.label(bottom,"OPACITY",18,83,size=10,bold=True,muted=True)
        self.opacity_label=self.label(bottom,f"{self.cfg['opacity']}%",533,83,size=10,bold=True)
        opacity=tk.Scale(bottom,from_=20,to=100,orient="horizontal",resolution=1,
                         bd=0,highlightthickness=0,showvalue=False,
                         bg=bottom.cget("bg"),troughcolor=self.colors["raised"],
                         activebackground=self.colors["accent"],sliderlength=18,length=655)
        opacity.set(self.cfg["opacity"])
        opacity.configure(command=self.set_opacity)
        opacity.place(x=19,y=115)
        self.label(bottom,"Drag a visible keycap to move the overlay. Right-click for more options.",20,157,size=10,muted=True)
        self.button(bottom,"Reset overlay position",self.reset_position,18,192,236,39)
        self.button(bottom,"Test both rows",self.test_overlay,264,192,160,39,primary=True)

    def change_position(self,pos):
        self.cfg["position"]=pos
        self.persist()
        self.overlay.placement()
        self.render_page()

    def reset_position(self):
        self.overlay.placement()
        self.test_overlay()

    def test_overlay(self):
        if not self.enabled:
            return
        self.overlay.show(["Ctrl","Shift","S"])
        self.overlay.show(["Left click ×2"], "mouse")

    def set_opacity(self, value):
        self.cfg["opacity"] = int(float(value))
        self.opacity_label.configure(text=f"{self.cfg['opacity']}%")
        self.overlay.draw()
        self.persist()

    def set_duration(self,value):
        self.cfg["duration"]=round(float(value),1)
        if hasattr(self,"duration_label") and self.duration_label.winfo_exists():
            self.duration_label.config(text=f"{self.cfg['duration']:.1f} seconds")
        self.persist()

    def page_settings(self):
        b=self.body
        self.label(b,"Simple controls. No background services.",27,4,size=11,muted=True)
        appearance=self.pane(b,25,41,727,165)
        self.label(appearance,"APP THEME",18,16,size=10,bold=True,muted=True)
        for i,name in enumerate(("Dark","Light","System")):
            self.button(appearance,name,lambda n=name:self.update_theme(n),18+i*231,62,217,48,
                        active=self.cfg["theme"]==name)
        self.label(appearance,"This changes the dashboard only. Overlay styles are separate.",19,130,size=9,muted=True)
        hotkeys=self.pane(b,25,223,727,180)
        self.label(hotkeys,"GLOBAL SHORTCUTS",18,16,size=10,bold=True,muted=True)
        self.label(hotkeys,"Ctrl + Shift + O",19,56,size=12,bold=True)
        self.label(hotkeys,"Pause or resume overlay",316,58,size=10,muted=True)
        self.label(hotkeys,"Ctrl + Shift + K",19,103,size=12,bold=True)
        self.label(hotkeys,"Show / hide dashboard",316,105,size=10,muted=True)
        note=self.pane(b,25,420,727,92)
        self.label(note,"Installation",18,15,size=12,bold=True)
        self.label(note,"Settings are stored on this computer.",18,50,size=10,muted=True)
        self.button(note,"Windows installed apps",self.open_installed_apps,485,27,220,38)

    def page_about(self):
        project = self.pane(self.body,25,5,727,213)
        self.label(project,APP,22,20,size=24,bold=True)
        self.label(project,f"Version {VERSION}   ·   Windows 10 / 11",24,61,size=10,muted=True)
        self.label(project,f"Built and maintained by {MAINTAINER}",24,106,size=13,bold=True)
        self.label(project,"@DipeshGoud on GitHub",24,135,size=10,muted=True)
        self.button(project,"GitHub profile",lambda:webbrowser.open("https://github.com/DipeshGoud"),
                    24,167,150,32)
        links = self.pane(self.body,25,235,727,173)
        self.label(links,"Project and license",22,18,size=15,bold=True)
        self.label(links,"The official Windows builds are free and distributed under the MIT License.",
                   24,53,size=10,muted=True)
        for index, (label, path) in enumerate((
                ("Source code",""), ("Report an issue","/issues/new"), ("MIT License","/blob/main/LICENSE"))):
            self.button(links,label,lambda suffix=path:webbrowser.open(REPOSITORY+suffix),
                        24+index*188,102,172,38,primary=index==0)

    def open_installed_apps(self):
        try:
            os.startfile("ms-settings:appsfeatures")
        except OSError as exc:
            messagebox.showerror(APP,str(exc),parent=self.root)

    def toggle(self):
        self.enabled=not self.enabled
        if not self.enabled:
            self.overlay.hide()
            self.click_ring.hide()
        self.render_shell()

    def hide_dashboard(self):
        self.root.withdraw()

    def show_dashboard(self):
        if self.root.state()=="withdrawn":
            self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def poll(self):
        try:
            for _ in range(50):
                try:item=self.messages.get_nowait()
                except queue.Empty:break
                if item[0]=="keyboard" and self.cfg["keyboard"] and self.enabled:
                    self.overlay.show(item[1])
                elif item[0]=="mouse" and self.enabled:
                    if self.cfg["mouse"]:
                        count = item[4]
                        label = f"{item[1]} ×{count}" if self.cfg["click_count"] and count > 1 else item[1]
                        self.overlay.show([label], "mouse")
                    if self.cfg["cursor_ring"]:
                        self.click_ring.show(item[2],item[3],self.colors["accent"])
                elif item[0]=="wheel" and self.cfg["wheel"] and self.enabled:
                    self.overlay.show([item[1]], "mouse")
                elif item[0]=="toggle":
                    self.toggle()
                elif item[0]=="dashboard":
                    if self.root.state()=="withdrawn":self.show_dashboard()
                    else:self.hide_dashboard()
                elif item[0]=="error":
                    self.enabled=False
                    self.overlay.hide()
                    self.click_ring.hide()
                    self.render_shell()
                    messagebox.showwarning("KeyHalo input unavailable",item[1],parent=self.root)
        finally:
            try:self.root.after(35,self.poll)
            except tk.TclError:pass

    def close(self):
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
            self.flush_settings()
        self.input.stop()
        self.overlay.close()
        self.click_ring.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if sys.platform != "win32":
        raise RuntimeError(f"{APP} requires Windows 10 or 11.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    for function in (kernel.SetEvent, kernel.ReleaseMutex, kernel.CloseHandle):
        function.argtypes = [wintypes.HANDLE]
        function.restype = wintypes.BOOL
    handles = []
    owns_mutex = False
    try:
        for name in ("Activate", "Stop"):
            event = kernel.CreateEventW(None, False, False, rf"Local\OpenDStroke.{name}")
            if not event:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(event)
        ctypes.set_last_error(0)
        mutex = kernel.CreateMutexW(None, True, r"Local\OpenDStroke.Instance")
        error = ctypes.get_last_error()
        if not mutex:
            raise ctypes.WinError(error)
        handles.append(mutex)
        owns_mutex = error != 183  # ERROR_ALREADY_EXISTS
        if not owns_mutex:
            owns_mutex = kernel.WaitForSingleObject(mutex, 0) in (0, 0x80)
        activate, stop = handles[:2]

        if "--stop" in sys.argv[1:]:
            if not owns_mutex:
                kernel.SetEvent(stop)
                result = kernel.WaitForSingleObject(mutex, 10000)
                owns_mutex = result in (0, 0x80)  # acquired or abandoned
                return 0 if owns_mutex else 1
            return 0
        if not owns_mutex:
            kernel.SetEvent(activate)
            return 0

        run_dashboard(kernel, activate, stop)
        return 0
    finally:
        if owns_mutex:
            kernel.ReleaseMutex(mutex)
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


def run_dashboard(kernel, activate, stop):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (OSError,AttributeError):
        pass
    app = OpenDStrokeApp()

    def check_commands():
        if kernel.WaitForSingleObject(stop, 0) == 0:
            app.close()
            return
        if kernel.WaitForSingleObject(activate, 0) == 0:
            app.show_dashboard()
            ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(int(app.root.wm_frame(), 0)))
        app.root.after(60, check_commands)

    app.root.after(60, check_commands)
    app.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        details=traceback.format_exc()
        # Save errors only, never any key presses or input event data.
        try:
            path=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/APP/"startup_error.log"
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(details,encoding="utf-8")
        except OSError:
            pass
        print(details,file=sys.stderr)
        if sys.platform=="win32":
            try:
                ctypes.windll.user32.MessageBoxW(None,
                    f"{APP} could not start. See %LOCALAPPDATA%\\{APP}\\startup_error.log for details.",
                    f"{APP} startup error",0x10)
            except Exception:
                pass
        sys.exit(1)
