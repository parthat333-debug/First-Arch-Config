#!/usr/bin/env python3
# WiFi panel: scan nearby networks with nmcli, connect with a click.
import os, re, subprocess, threading
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GLib, GtkLayerShell

def nmcli(*args):
    r = subprocess.run(["nmcli", *args], capture_output=True, text=True)
    return r.returncode, (r.stdout or r.stderr).strip()

def scan():
    _, out = nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes")
    _, saved = nmcli("-t", "-f", "NAME", "con", "show")
    saved = set(saved.splitlines())
    nets = {}
    for line in out.splitlines():
        parts = [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]
        if len(parts) < 4 or not parts[1]:
            continue
        inuse, ssid, signal, security = parts[0] == "*", parts[1], int(parts[2] or 0), parts[3]
        if ssid not in nets or signal > nets[ssid]["signal"]:
            nets[ssid] = dict(inuse=inuse, signal=signal, secure=bool(security), saved=ssid in saved)
    return sorted(nets.items(), key=lambda n: (not n[1]["inuse"], -n[1]["signal"]))

def bars(signal):
    return "▂▄▆█"[:max(1, (signal + 24) // 25)].ljust(4, "·")

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="WiFi")
        screen = self.get_screen()
        self.set_visual(screen.get_rgba_visual())
        self.set_app_paintable(True)
        css = Gtk.CssProvider()
        css.load_from_path(os.path.expanduser("~/.config/theme/panel-style.css"))
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "theme-panel")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 60)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.connect("key-press-event", lambda w, e: e.keyval == 65307 and w.destroy())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("panel-box")
        box.set_size_request(400, 520)
        self.add(box)

        top = Gtk.Box(spacing=6)
        top.add(Gtk.Label(label="<b>WiFi</b>", use_markup=True, xalign=0, hexpand=True))
        self.toggle = Gtk.Button()
        self.toggle.connect("clicked", self.toggle_wifi)
        rescan = Gtk.Button(label="Scan again")
        rescan.connect("clicked", lambda _b: self.start_scan())
        top.add(self.toggle)
        top.add(rescan)
        box.add(top)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.add(self.list)
        box.add(scroll)
        self.status = Gtk.Label(xalign=0, wrap=True, max_width_chars=50)
        box.add(self.status)
        self.start_scan()

    def wifi_on(self):
        return nmcli("radio", "wifi")[1] == "enabled"

    def toggle_wifi(self, _btn):
        nmcli("radio", "wifi", "off" if self.wifi_on() else "on")
        GLib.timeout_add(2000, lambda: self.start_scan() and False)

    def start_scan(self):
        on = self.wifi_on()
        self.toggle.set_label("Turn off" if on else "Turn on")
        for child in self.list.get_children():
            self.list.remove(child)
        if not on:
            self.status.set_text("WiFi is off.")
            return
        self.status.set_text("Scanning…")
        threading.Thread(target=lambda: GLib.idle_add(self.show, scan()), daemon=True).start()

    def show(self, nets):
        self.status.set_text(f"{len(nets)} networks found." if nets else "No networks found.")
        for ssid, n in nets:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=4)
            line = Gtk.Box(spacing=8)
            lock = "\uf023 " if n["secure"] else ""
            line.add(Gtk.Label(label=f"{bars(n['signal'])}  {lock}{ssid}", xalign=0, hexpand=True))
            btn = Gtk.Button(label="Disconnect" if n["inuse"] else "Connect")
            line.add(btn)
            row.add(line)
            entry = Gtk.Entry(visibility=False, placeholder_text="Password, then Enter", no_show_all=True)
            row.add(entry)
            btn.connect("clicked", self.on_click, ssid, n, entry)
            entry.connect("activate", lambda e, s=ssid: self.connect_new(s, e.get_text()))
            self.list.add(row)
        self.list.show_all()

    def on_click(self, _btn, ssid, n, entry):
        if n["inuse"]:
            self.run(f"Disconnecting from {ssid}…", "con", "down", "id", ssid)
        elif n["saved"]:
            self.run(f"Connecting to {ssid}…", "con", "up", "id", ssid)
        elif n["secure"]:
            entry.show()
            entry.grab_focus()
        else:
            self.run(f"Connecting to {ssid}…", "dev", "wifi", "connect", ssid)

    def connect_new(self, ssid, password):
        self.run(f"Connecting to {ssid}…", "dev", "wifi", "connect", ssid, "password", password)

    def run(self, message, *args):
        self.status.set_text(message)
        def work():
            code, out = nmcli(*args)
            GLib.idle_add(self.done, code, out)
        threading.Thread(target=work, daemon=True).start()

    def done(self, code, out):
        self.status.set_text(("✓ " if code == 0 else "✗ ") + out[:160])
        self.start_scan()

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
