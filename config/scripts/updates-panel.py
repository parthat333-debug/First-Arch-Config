#!/usr/bin/env python3
# Updates panel: pending official, AUR and firmware updates, with one-click update.
import json, os, subprocess, threading, time
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GLib, GtkLayerShell

REBOOT_PKGS = {"linux", "linux-lts", "linux-zen", "linux-firmware", "intel-ucode", "systemd"}

def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()

def parse(out):
    pkgs = []
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 4 and p[2] == "->":
            pkgs.append((p[0], p[1], p[3]))
    return pkgs

def firmware():
    code, out = run("fwupdmgr", "get-updates", "--json")
    if code != 0 or not out:
        return []
    try:
        devices = json.loads(out).get("Devices", [])
    except ValueError:
        return []
    fw = []
    for d in devices:
        rel = d.get("Releases") or [{}]
        fw.append((d.get("Name", "Device"), d.get("Version", "?"), rel[0].get("Version", "?")))
    return fw

def advisories():
    fixable = {l.split()[0] for l in run("arch-audit", "-u")[1].splitlines() if l.strip()}
    adv = []
    for line in run("arch-audit")[1].splitlines():
        p = line.split()
        if len(p) >= 3 and "risk" in line:
            risk = next((w for w in ("Critical", "High", "Medium", "Low") if w in line), "?")
            adv.append((p[0], risk, p[0] in fixable))
    return adv

def check():
    return parse(run("checkupdates")[1]), parse(run("yay", "-Qua")[1]), firmware(), advisories()

def refresh_bar():
    subprocess.run(["pkill", "-RTMIN+9", "waybar"])

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Updates")
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
        box.set_size_request(420, 560)
        self.add(box)

        top = Gtk.Box(spacing=6)
        top.add(Gtk.Label(label="<b>\uf021  Updates</b>", use_markup=True, xalign=0, hexpand=True))
        self.checked = Gtk.Label(xalign=1)
        top.add(self.checked)
        box.add(top)

        self.counts = Gtk.Label(xalign=0)
        box.add(self.counts)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.add(self.list)
        box.add(scroll)

        self.note = Gtk.Label(xalign=0, wrap=True, max_width_chars=50)
        box.add(self.note)

        btns = Gtk.Box(spacing=8, homogeneous=True)
        self.update_btn = Gtk.Button(label="Update all")
        self.update_btn.connect("clicked", lambda _b: self.in_terminal("yay -Syu"))
        self.fw_btn = Gtk.Button(label="Update firmware", no_show_all=True)
        self.fw_btn.connect("clicked", lambda _b: self.in_terminal("fwupdmgr update"))
        again = Gtk.Button(label="Check now")
        again.connect("clicked", lambda _b: self.start_check())
        for b in (self.update_btn, self.fw_btn, again):
            btns.add(b)
        box.add(btns)
        self.start_check()

    def start_check(self):
        for child in self.list.get_children():
            self.list.remove(child)
        self.counts.set_text("Checking…")
        self.note.set_text("")
        threading.Thread(target=lambda: GLib.idle_add(self.show, *check()), daemon=True).start()

    def section(self, title, items):
        if not items:
            return
        self.list.add(Gtk.Label(label=f"<b>{title}</b>", use_markup=True, xalign=0, margin_top=6))
        for name, old, new in items:
            row = Gtk.Box(spacing=8, margin=3)
            mark = "\uf071 " if name in REBOOT_PKGS else ""
            row.add(Gtk.Label(label=f"{mark}{name}", xalign=0, hexpand=True))
            row.add(Gtk.Label(label=f"{old} → {new}", xalign=1))
            self.list.add(row)

    def show(self, repo, aur, fw, adv):
        self.checked.set_text("checked " + time.strftime("%H:%M"))
        self.counts.set_text(f"Official {len(repo)}   ·   AUR {len(aur)}   ·   Firmware {len(fw)}")
        self.section("Official", repo)
        self.section("AUR (user-made, check before updating)", aur)
        self.section("Firmware", fw)
        if adv:
            by = {r: sum(a[1] == r for a in adv) for r in ("Critical", "High", "Medium", "Low")}
            summary = "  ·  ".join(f"{n} {r}" for r, n in by.items() if n)
            self.list.add(Gtk.Label(label=f"<b>Security advisories</b>  ({summary})",
                                    use_markup=True, xalign=0, margin_top=6))
            for name, risk, fix in sorted(adv, key=lambda a: not a[2]):
                row = Gtk.Box(spacing=8, margin=3)
                row.add(Gtk.Label(label=("\uf071 " if fix else "") + name, xalign=0, hexpand=True))
                row.add(Gtk.Label(label=f"{risk} · {'fix available, update now' if fix else 'no fix yet'}", xalign=1))
                self.list.add(row)
        if not (repo or aur or fw):
            self.list.add(Gtk.Label(label="\uf00c  Everything is up to date", margin=20))
        if any(n in REBOOT_PKGS for n, _o, _v in repo):
            self.note.set_text("\uf071  Includes kernel/firmware/system updates: reboot after updating.")
        self.update_btn.set_sensitive(bool(repo or aur))
        self.fw_btn.set_visible(bool(fw))
        self.list.show_all()
        refresh_bar()

    def in_terminal(self, cmd):
        def work():
            subprocess.run(["kitty", "--class", "kitty-float", "sh", "-c",
                            f"{cmd}; echo; read -p 'Done. Press Enter to close…' _"])
            GLib.idle_add(self.start_check)
        threading.Thread(target=work, daemon=True).start()

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
