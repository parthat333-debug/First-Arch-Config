#!/usr/bin/env python3
# Look panel: gaps, border, rounding, border gradient and animations. Saves into hyprland.lua.
import json, os, re, shutil, subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

HYPR = os.path.expanduser("~/.config/hypr/hyprland.lua")
BAK = HYPR + ".look.bak"
LOOK = os.path.expanduser("~/.config/hypr/look.json")
THEME = os.path.expanduser("~/.config/theme/current.json")
PRESETS = {
    "Tight":    dict(gaps_in=3, gaps_out=6, border=1, rounding=4, ws_speed=1.2, ws_style="fade"),
    "Balanced": dict(gaps_in=6, gaps_out=12, border=2, rounding=12, ws_speed=2.5, ws_style="slide"),
    "Floaty":   dict(gaps_in=10, gaps_out=20, border=2, rounding=18, ws_speed=3.5, ws_style="slide"),
}
WS_STYLES = ["fade", "slide", "slidevert", "slidefade"]

def num(text, key, default):
    m = re.search(rf"\b{key}\s*=\s*([\d.]+)", text)
    return float(m.group(1)) if m else default

def load():
    text = open(HYPR).read()
    d = dict(gaps_in=num(text, "gaps_in", 3), gaps_out=num(text, "gaps_out", 5),
             border=num(text, "border_size", 1), rounding=num(text, "rounding", 3),
             anim=True, ws_speed=1.94, ws_style="fade", grad=False, grad2="#00ff99", angle=45)
    try:
        d.update(json.load(open(LOOK)))
    except Exception:
        pass
    return d

def accent():
    try:
        return json.load(open(THEME))["accent"]
    except Exception:
        return "#33ccff"

def border_line(look):
    a = f"rgba({accent()[1:]}ee)"
    if look.get("grad"):
        return (f'active_border   = {{ colors = {{"{a}", "rgba({look["grad2"][1:]}ee)"}}, '
                f'angle = {int(look["angle"])} }},')
    return f'active_border   = "{a}",'

def errors():
    return subprocess.run(["hyprctl", "configerrors"], capture_output=True, text=True).stdout

def write(look):
    text = open(HYPR).read()
    for key, val in [("gaps_in", look["gaps_in"]), ("gaps_out", look["gaps_out"]),
                     ("border_size", look["border"]), ("rounding", look["rounding"])]:
        text = re.sub(rf"(\b{key}\s*=\s*)[\d.]+", lambda m, v=val: m.group(1) + str(int(v)), text, count=1)
    text = re.sub(r"(?<!in)active_border\s*=.*", lambda m: border_line(look), text, count=1)
    for leaf in ("workspaces", "workspacesIn", "workspacesOut"):
        text = re.sub(rf'(leaf = "{leaf}",\s+enabled = )\w+(,\s+speed = )[\d.]+(.*?style = )"[^"]*"',
                      lambda m: f'{m.group(1)}true{m.group(2)}{look["ws_speed"]:.2f}{m.group(3)}"{look["ws_style"]}"',
                      text, count=1)
    text = re.sub(r'(leaf = "global",\s+enabled = )\w+',
                  lambda m: m.group(1) + ("true" if look["anim"] else "false"), text, count=1)
    before = errors()
    shutil.copy(HYPR, BAK)
    open(HYPR, "w").write(text)
    subprocess.run(["hyprctl", "reload"], capture_output=True)
    if errors() != before:
        shutil.copy(BAK, HYPR)
        subprocess.run(["hyprctl", "reload"], capture_output=True)
        return False
    json.dump(look, open(LOOK, "w"), indent=2)
    return True

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Look")
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
        self.look = load()
        self.pending = None
        self.widgets = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.get_style_context().add_class("panel-box")
        box.set_size_request(420, -1)
        self.add(box)

        box.add(Gtk.Label(label="<b>Presets</b>", use_markup=True, xalign=0))
        presets = Gtk.Box(spacing=6, homogeneous=True)
        for name in PRESETS:
            btn = Gtk.Button(label=name)
            btn.connect("clicked", self.on_preset, name)
            presets.add(btn)
        box.add(presets)

        box.add(Gtk.Label(label="<b>Windows</b>", use_markup=True, xalign=0))
        for key, label, lo, hi in [("gaps_in", "Gaps between", 0, 20), ("gaps_out", "Gaps to edge", 0, 40),
                                   ("border", "Border size", 0, 8), ("rounding", "Rounding", 0, 30)]:
            box.add(self.slider(key, label, lo, hi, 1))

        box.add(Gtk.Label(label="<b>Border gradient</b>  (first colour = theme accent)", use_markup=True, xalign=0))
        row = Gtk.Box(spacing=8)
        row.add(Gtk.Label(label="Gradient", width_chars=14, xalign=0))
        grad = Gtk.Switch(active=self.look["grad"])
        grad.connect("notify::active", lambda s, _p: self.set("grad", s.get_active()))
        row.add(grad)
        rgba = Gdk.RGBA()
        rgba.parse(self.look["grad2"])
        color = Gtk.ColorButton(rgba=rgba)
        color.connect("color-set", self.on_color)
        row.add(Gtk.Label(label="Second colour", hexpand=True, xalign=1))
        row.add(color)
        box.add(row)
        box.add(self.slider("angle", "Angle", 0, 360, 5))

        box.add(Gtk.Label(label="<b>Animations</b>", use_markup=True, xalign=0))
        row = Gtk.Box(spacing=8)
        row.add(Gtk.Label(label="Animations", width_chars=14, xalign=0, hexpand=True))
        anim = Gtk.Switch(active=self.look["anim"])
        anim.connect("notify::active", lambda s, _p: self.set("anim", s.get_active()))
        row.add(anim)
        box.add(row)
        row = Gtk.Box(spacing=8)
        row.add(Gtk.Label(label="Workspace switch", width_chars=14, xalign=0, hexpand=True))
        style = Gtk.ComboBoxText()
        for s in WS_STYLES:
            style.append_text(s)
        style.set_active(WS_STYLES.index(self.look["ws_style"]) if self.look["ws_style"] in WS_STYLES else 0)
        style.connect("changed", lambda c: self.set("ws_style", c.get_active_text()))
        self.widgets["ws_style"] = style
        row.add(style)
        box.add(row)
        box.add(self.slider("ws_speed", "Switch speed", 0.5, 6, 0.1, "fast ← → slow"))

        self.status = Gtk.Label(xalign=0, wrap=True)
        box.add(self.status)

    def slider(self, key, label, lo, hi, step, hint=None):
        row = Gtk.Box(spacing=8)
        row.add(Gtk.Label(label=label, width_chars=14, xalign=0))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        scale.set_value(self.look[key])
        scale.set_digits(1 if step < 1 else 0)
        scale.set_hexpand(True)
        if hint:
            scale.set_tooltip_text(hint)
        scale.connect("value-changed", lambda s: self.set(key, round(s.get_value(), 2)))
        self.widgets[key] = scale
        row.add(scale)
        return row

    def set(self, key, value):
        self.look[key] = value
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(300, self.apply)

    def apply(self):
        self.pending = None
        ok = write(self.look)
        self.status.set_text("✓ Applied and saved." if ok else "✗ That caused a config error, so it was undone.")
        return False

    def on_color(self, btn):
        c = btn.get_rgba()
        self.set("grad2", "#%02x%02x%02x" % (int(c.red * 255), int(c.green * 255), int(c.blue * 255)))

    def on_preset(self, _btn, name):
        self.look.update(PRESETS[name])
        for key, w in self.widgets.items():
            if key == "ws_style":
                w.set_active(WS_STYLES.index(self.look["ws_style"]))
            else:
                w.set_value(self.look[key])
        self.set("ws_speed", self.look["ws_speed"])

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
