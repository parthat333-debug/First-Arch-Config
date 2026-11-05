#!/usr/bin/env python3
import json, os, re, shutil, subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

T = os.path.expanduser("~/.config/theme")
HYPR = os.path.expanduser("~/.config/hypr/hyprland.lua")
CURRENT, SAVED = f"{T}/current.json", f"{T}/presets.json"

PRESETS = {
    "Default":     dict(bg="#14141e", fg="#e0e0e0", muted="#888888", accent="#ffffff", danger="#ff6b6b"),
    "Nord":        dict(bg="#2e3440", fg="#eceff4", muted="#4c566a", accent="#88c0d0", danger="#bf616a"),
    "Catppuccin":  dict(bg="#1e1e2e", fg="#cdd6f4", muted="#6c7086", accent="#cba6f7", danger="#f38ba8"),
    "Gruvbox":     dict(bg="#282828", fg="#ebdbb2", muted="#928374", accent="#fabd2f", danger="#fb4934"),
    "Tokyo Night": dict(bg="#1a1b26", fg="#c0caf5", muted="#565f89", accent="#7aa2f7", danger="#f7768e"),
}
COLORS = [("bg", "Background"), ("fg", "Text"), ("accent", "Accent"),
          ("muted", "Inactive"), ("danger", "Warning"),
          ("panel_bg", "Panel background"),
          ("ws_fg", "Workspace numbers"), ("ws_active", "Active workspace")]

def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default

def apply(s):
    r, g, b = (int(s["bg"][i:i + 2], 16) for i in (1, 3, 5))
    with open(f"{T}/colors.css", "w") as f:
        f.write(f"@define-color bar_bg rgba({r}, {g}, {b}, {s['bar']:.2f});\n@define-color bg {s['bg']};\n"
                f"@define-color fg {s['fg']};\n@define-color muted {s['muted']};\n"
                f"@define-color accent {s['accent']};\n@define-color danger {s['danger']};\n")
    pr, pg, pb = (int(s["panel_bg"][i:i + 2], 16) for i in (1, 3, 5))
    with open(f"{T}/colors.css", "a") as f:
        f.write(f"@define-color panel_bg rgba({pr}, {pg}, {pb}, {s['panel']:.2f});\n")
    with open(f"{T}/colors.css", "a") as f:
        f.write(f"@define-color ws_fg {s['ws_fg']};\n@define-color ws_active {s['ws_active']};\n")
    ids = ", ".join(f"#custom-ws{i}" for i in range(1, 11))
    with open(f"{T}/bar-extra.css", "w") as f:
        f.write(f"{ids} {{ font-size: {int(s['ws_size'])}px; }}\n")
    with open(f"{T}/colors.conf", "w") as f:
        f.write(f"background {s['bg']}\nforeground {s['fg']}\ncursor {s['accent']}\n"
                f"selection_background {s['muted']}\nbackground_opacity {s['term']:.2f}\n")
    with open(f"{T}/colors.rasi", "w") as f:
        f.write(f"* {{ bg: rgba({r}, {g}, {b}, {s['bar']:.2f}); fg: {s['fg']}; "
                f"accent: {s['accent']}; muted: {s['muted']}; }}\n")
    subprocess.run(["pkill", "-USR1", "kitty"])
    subprocess.run(["swaync-client", "-rs"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("gsettings set org.gnome.desktop.interface gtk-theme Adwaita && gsettings set org.gnome.desktop.interface gtk-theme Adwaita-dark", shell=True)

    lua = open(HYPR).read()
    try:
        look = json.load(open(os.path.expanduser("~/.config/hypr/look.json")))
    except Exception:
        look = {}
    a = f'rgba({s["accent"][1:]}ee)'
    if look.get("grad"):
        line = f'active_border   = {{ colors = {{"{a}", "rgba({look["grad2"][1:]}ee)"}}, angle = {int(look.get("angle", 45))} }},'
    else:
        line = f'active_border   = "{a}",'
    new = re.sub(r'(?<!in)active_border\s*=.*', lambda m: line, lua, count=1)
    new = re.sub(r'inactive_border\s*=.*', f'inactive_border = "rgba({s["muted"][1:]}aa)",', new, count=1)
    if new != lua:
        if not os.path.exists(HYPR + ".bak"):
            shutil.copy(HYPR, HYPR + ".bak")
        open(HYPR, "w").write(new)
        subprocess.run(["hyprctl", "reload"], stdout=subprocess.DEVNULL)
    json.dump(s, open(CURRENT, "w"), indent=2)

def to_hex(c):
    return "#%02x%02x%02x" % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Theme")
        screen = self.get_screen()
        self.set_visual(screen.get_rgba_visual())
        self.set_app_paintable(True)
        self.css = Gtk.CssProvider()
        self.css.load_from_path(os.path.expanduser("~/.config/theme/panel-style.css"))
        Gtk.StyleContext.add_provider_for_screen(screen, self.css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "theme-panel")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 60)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.connect("key-press-event", lambda w, e: e.keyval == Gdk.KEY_Escape and w.destroy())
        self.s = {**dict(PRESETS["Default"], term=0.85, bar=0.55, panel=0.75, panel_bg="#14141e",
                       ws_fg="#cccccc", ws_active="#ffffff", ws_size=14),
                  **load(CURRENT, {})}
        self.pending = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.get_style_context().add_class("panel-box")
        self.add(box)

        box.add(Gtk.Label(label="<b>Presets</b>", use_markup=True, xalign=0))
        self.flow = Gtk.FlowBox(max_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE)
        box.add(self.flow)
        self.fill_presets()

        box.add(Gtk.Label(label="<b>Colours</b>", use_markup=True, xalign=0))
        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        box.add(grid)
        self.buttons = {}
        for row, (key, label) in enumerate(COLORS):
            btn = Gtk.ColorButton(rgba=self.rgba(self.s[key]))
            btn.connect("color-set", self.on_color, key)
            self.buttons[key] = btn
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(btn, 1, row, 1, 1)

        box.add(Gtk.Label(label="<b>Transparency</b>  (left = more see-through)", use_markup=True, xalign=0))
        for key, label in [("term", "Terminal"), ("bar", "Status bar"), ("panel", "Panels")]:
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05)
            scale.set_value(self.s[key])
            scale.set_hexpand(True)
            scale.connect("value-changed", self.on_slider, key)
            row = Gtk.Box(spacing=8)
            row.add(Gtk.Label(label=label, width_chars=10, xalign=0))
            row.add(scale)
            box.add(row)

        look_btn = Gtk.Button(label="Windows, borders and animations…")
        look_btn.connect("clicked", lambda _b: (subprocess.Popen([os.path.expanduser("~/.config/scripts/look-panel.py")]), self.destroy()))
        box.add(look_btn)
        size_row = Gtk.Box(spacing=8)
        size_row.add(Gtk.Label(label="Workspace size", width_chars=10, xalign=0))
        size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 24, 1)
        size.set_value(self.s["ws_size"])
        size.set_hexpand(True)
        size.connect("value-changed", self.on_slider, "ws_size")
        size_row.add(size)
        box.add(size_row)
        save = Gtk.Button(label="Save as preset…")
        save.connect("clicked", self.on_save)
        box.add(save)

    def rgba(self, h):
        c = Gdk.RGBA()
        c.parse(h)
        return c

    def fill_presets(self):
        for child in self.flow.get_children():
            self.flow.remove(child)
        for name, p in {**PRESETS, **load(SAVED, {})}.items():
            btn = Gtk.Button(label=name)
            btn.connect("clicked", self.on_preset, p)
            self.flow.add(btn)
        self.flow.show_all()

    def schedule(self):
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(250, self.run_apply)

    def run_apply(self):
        self.pending = None
        apply(self.s)
        self.css.load_from_path(os.path.expanduser("~/.config/theme/panel-style.css"))
        return False

    def on_preset(self, _btn, p):
        self.s.update(p)
        for key, btn in self.buttons.items():
            btn.set_rgba(self.rgba(self.s[key]))
        self.schedule()

    def on_color(self, btn, key):
        self.s[key] = to_hex(btn.get_rgba())
        self.schedule()

    def on_slider(self, scale, key):
        self.s[key] = round(scale.get_value(), 2)
        self.schedule()

    def on_save(self, _btn):
        dialog = Gtk.Dialog(title="Preset name", transient_for=self)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        entry = Gtk.Entry(activates_default=True)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.get_content_area().add(entry)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK and entry.get_text().strip():
            saved = load(SAVED, {})
            saved[entry.get_text().strip()] = {k: self.s[k] for k, _ in COLORS}
            json.dump(saved, open(SAVED, "w"), indent=2)
            self.fill_presets()
        dialog.destroy()

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
