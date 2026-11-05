#!/usr/bin/env python3
# Security panel: ClamAV status, one-click scans with live output, definitions update.
import datetime, os, re, subprocess, threading
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GLib, GtkLayerShell

LOG = os.path.expanduser("~/.local/share/hypr-panels/av-last-scan.txt")
LYNIS = os.path.expanduser("~/.local/share/hypr-panels/lynis-summary.txt")
TARGETS = [("Downloads", os.path.expanduser("~/Downloads")),
           ("External drive", "/mnt/passport"),
           ("Whole home (slow)", os.path.expanduser("~"))]

def definitions():
    out = subprocess.run(["clamscan", "--version"], capture_output=True, text=True).stdout.strip()
    parts = out.split("/")
    return (parts[0], parts[1], parts[2]) if len(parts) >= 3 else (out or "ClamAV not found", "?", "?")

def updater_on():
    r = subprocess.run(["systemctl", "is-active", "clamav-freshclam"], capture_output=True, text=True)
    return r.stdout.strip() == "active"

def last_audit():
    try:
        lines = open(LYNIS).read().splitlines()
    except Exception:
        return "No audit yet"
    score = next((l.split("=", 1)[1] for l in lines if l.startswith("hardening_index=")), "?")
    warns = sum(l.startswith("warning[]=") for l in lines)
    tips = sum(l.startswith("suggestion[]=") for l in lines)
    when = datetime.datetime.fromtimestamp(os.path.getmtime(LYNIS)).strftime("%d %b %H:%M")
    return f"Score {score}/100 · {warns} warning(s) · {tips} suggestion(s) ({when})"

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Security")
        screen = self.get_screen()
        self.set_visual(screen.get_rgba_visual())
        self.set_app_paintable(True)
        css = Gtk.CssProvider()
        css.load_from_path(os.path.expanduser("~/.config/theme/panel-style.css"))
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        mono = Gtk.CssProvider()
        mono.load_from_data(b"textview, textview text { font-family: monospace; font-size: 11px;"
                            b" background-color: transparent; color: @fg; }")
        Gtk.StyleContext.add_provider_for_screen(screen, mono, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "theme-panel")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 60)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.connect("key-press-event", lambda w, e: e.keyval == 65307 and w.destroy())
        self.proc = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("panel-box")
        box.set_size_request(480, 620)
        self.add(box)
        box.add(Gtk.Label(label="<b>\uf132  Security</b>", use_markup=True, xalign=0))

        grid = Gtk.Grid(column_spacing=16, row_spacing=4)
        box.add(grid)
        self.info = {}
        for row, name in enumerate(["Engine", "Definitions", "Last updated", "Auto-update", "Last scan", "Last audit"]):
            grid.attach(Gtk.Label(label=name, xalign=0), 0, row, 1, 1)
            self.info[name] = Gtk.Label(xalign=0, wrap=True, max_width_chars=40)
            grid.attach(self.info[name], 1, row, 1, 1)

        box.add(Gtk.Label(label="<b>Scan</b>", use_markup=True, xalign=0))
        quick = Gtk.Box(spacing=6, homogeneous=True)
        self.target_btns = []
        for label, path in TARGETS:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", lambda _b, p=path: self.scan(p))
            self.target_btns.append((btn, path))
            quick.add(btn)
        box.add(quick)
        custom = Gtk.Box(spacing=6)
        self.path_in = Gtk.Entry(placeholder_text="/home/parth/some/folder", hexpand=True)
        self.path_in.connect("activate", lambda e: self.scan(os.path.expanduser(e.get_text().strip())))
        go = Gtk.Button(label="Scan folder")
        go.connect("clicked", lambda _b: self.scan(os.path.expanduser(self.path_in.get_text().strip())))
        custom.add(self.path_in)
        custom.add(go)
        box.add(custom)

        actions = Gtk.Box(spacing=6)
        self.stop_btn = Gtk.Button(label="Stop scan")
        self.stop_btn.connect("clicked", self.stop)
        update = Gtk.Button(label="Update definitions now")
        update.connect("clicked", lambda _b: subprocess.Popen(
            ["kitty", "--hold", "sh", "-c", "sudo freshclam"]))
        audit = Gtk.Button(label="Security audit")
        audit.connect("clicked", self.audit)
        actions.add(self.stop_btn)
        actions.add(update)
        actions.add(audit)
        box.add(actions)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.out = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.CHAR)
        scroll.add(self.out)
        box.add(scroll)
        self.status = Gtk.Label(xalign=0, wrap=True)
        box.add(self.status)
        self.refresh()

    def refresh(self):
        engine, number, date = definitions()
        self.info["Engine"].set_text(engine)
        self.info["Definitions"].set_text(f"#{number}")
        self.info["Last updated"].set_text(date)
        self.info["Auto-update"].set_text("✓ on" if updater_on() else "✗ off")
        try:
            self.info["Last scan"].set_text(open(LOG).read().strip())
        except Exception:
            self.info["Last scan"].set_text("No scans yet")
        self.info["Last audit"].set_text(last_audit())
        for btn, path in self.target_btns:
            btn.set_sensitive(os.path.isdir(path) and (path != "/mnt/passport" or os.path.ismount(path)))
        self.stop_btn.set_sensitive(self.proc is not None)

    def audit(self, _btn):
        os.makedirs(os.path.dirname(LYNIS), exist_ok=True)
        cmd = (f"sudo lynis audit system --quick && "
               f"sudo grep -E '^(hardening_index|warning\\[\\]|suggestion\\[\\])=' /var/log/lynis-report.dat > {LYNIS}; "
               f"echo; read -p 'Done. Press Enter to close…' _")
        self.status.set_text("Security audit running in the terminal…")
        def work():
            subprocess.run(["kitty", "--class", "kitty-float", "sh", "-c", cmd])
            GLib.idle_add(self.refresh)
            GLib.idle_add(self.status.set_text, "Audit finished: " + last_audit())
        threading.Thread(target=work, daemon=True).start()

    def append(self, text):
        buf = self.out.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        self.out.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)

    def scan(self, path):
        if self.proc:
            return
        if not path or not os.path.exists(path):
            self.status.set_text(f"✗ Not found: {path}")
            return
        self.out.get_buffer().set_text("")
        self.status.set_text(f"Scanning {path}…  (only infected files are listed)")
        self.proc = subprocess.Popen(["clamscan", "-r", "-i", path], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.refresh()
        threading.Thread(target=self.read, args=(path,), daemon=True).start()

    def read(self, path):
        lines = []
        for line in self.proc.stdout:
            lines.append(line)
            GLib.idle_add(self.append, line)
        self.proc.wait()
        GLib.idle_add(self.finished, path, "".join(lines))

    def finished(self, path, text):
        stopped = self.proc.returncode not in (0, 1)
        self.proc = None
        infected = re.search(r"Infected files:\s*(\d+)", text)
        scanned = re.search(r"Scanned files:\s*(\d+)", text)
        n = int(infected.group(1)) if infected else 0
        when = datetime.datetime.now().strftime("%d %b %H:%M")
        if stopped and not infected:
            result = f"Stopped ({path})"
        elif n:
            result = f"⚠ {n} infected file(s) in {path} ({when})"
        else:
            result = f"✓ Clean: {scanned.group(1) if scanned else '?'} files in {path} ({when})"
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        open(LOG, "w").write(result)
        self.status.set_text(result)
        subprocess.Popen(["notify-send", "Virus scan finished", result])
        self.refresh()

    def stop(self, _btn):
        if self.proc:
            self.proc.terminate()

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
