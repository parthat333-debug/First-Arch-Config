#!/usr/bin/env python3
# Keybind panel: click a key button, press the new combo, done.
import os, re, shutil, subprocess, sys
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

CFG = os.path.expanduser("~/.config/hypr/hyprland.lua")
BAK = CFG + ".keybinds.bak"
CMDS = os.path.expanduser("~/.config/scripts/commands.txt")
MODIFIER_KEYS = {"Super_L", "Super_R", "Shift_L", "Shift_R", "Control_L", "Control_R",
                 "Alt_L", "Alt_R", "Meta_L", "Meta_R", "ISO_Level3_Shift"}

def pretty(expr):
    expr = expr.replace('mainMod .. " + ', "SUPER + ").replace(" .. key", "<number>")
    return expr.replace('" .. "', "").replace('"', "").strip()

NAMES = {"SUPER": "Win", "SHIFT": "Shift", "CTRL": "Ctrl", "ALT": "Alt", "Return": "Enter",
         "Delete": "Del", "Print": "PrtSc", "Escape": "Esc", "space": "Space", "Tab": "Tab",
         "left": "\u2190", "right": "\u2192", "up": "\u2191", "down": "\u2193",
         "mouse:272": "Left drag", "mouse:273": "Right drag",
         "mouse_down": "Scroll down", "mouse_up": "Scroll up", "<number>": "1\u20130",
         "XF86AudioRaiseVolume": "Volume up", "XF86AudioLowerVolume": "Volume down",
         "XF86AudioMute": "Mute key", "XF86AudioMicMute": "Mic mute key",
         "XF86MonBrightnessUp": "Brightness up", "XF86MonBrightnessDown": "Brightness down",
         "XF86AudioNext": "Next track key", "XF86AudioPrev": "Previous track key",
         "XF86AudioPlay": "Play key", "XF86AudioPause": "Pause key"}

def friendly(combo):
    """Display-only names, e.g. 'SUPER + SHIFT + Return' -> 'Win + Shift + Enter'."""
    return " + ".join(NAMES.get(k.strip(), k.strip()) for k in combo.split(" + "))

def to_expr(combo):
    if combo.startswith("SUPER + "):
        return 'mainMod .. " + ' + combo[len("SUPER + "):] + '"'
    return '"' + combo + '"'

def errors():
    return subprocess.run(["hyprctl", "configerrors"], capture_output=True, text=True).stdout

def read_binds():
    lines = open(CFG).read().split("\n")
    binds = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("hl.bind(") and ", hl.dsp." in s:
            start = line.index("hl.bind(") + len("hl.bind(")
            end = line.index(", hl.dsp.")
            action = line[end + len(", hl.dsp."):].strip()
            action = re.sub(r",\s*\{[^}]*\}\s*\)$", ")", action).rstrip(")")
            binds.append((i, line[start:end], start, end, action))
    return lines, binds

KNOWN = [
    (r"exec_cmd\(terminal", "Open terminal"), (r"exec_cmd\(fileManager", "Open file manager"),
    (r"exec_cmd\(menu", "App launcher"), (r"window\.close", "Close window"),
    (r"window\.float", "Float / unfloat window"), (r"fullscreen", "Fullscreen"),
    (r"pseudo", "Pseudo-tile window"), (r"togglesplit|layout", "Toggle split direction"),
    (r'focus\(\{ direction = "(\w+)"', "Focus window \\1"),
    (r'focus\(\{ workspace = "e\+1"', "Next workspace"), (r'focus\(\{ workspace = "e-1"', "Previous workspace"),
    (r"focus\(\{ workspace = i", "Switch to workspace"),
    (r'window\.move\(\{ workspace = "special', "Move window to scratchpad"),
    (r"window\.move\(\{ workspace = i", "Move window to workspace"),
    (r"toggle_special", "Show / hide scratchpad"),
    (r"window\.drag|mouse.*move", "Move window (drag)"), (r"window\.resize|mouse.*resize", "Resize window (drag)"),
    (r"exit", "Log out"), (r"grim -g", "Screenshot (select area)"), (r"grim", "Screenshot (full screen)"),
    (r"output-volume raise|5%\+.*SINK", "Volume up"), (r"output-volume lower|5%-.*SINK", "Volume down"),
    (r"output-volume mute", "Mute speakers"), (r"input-volume mute|SOURCE", "Mute microphone"),
    (r"brightness raise|brightnessctl.*\+", "Brightness up"), (r"brightness lower|brightnessctl.*-", "Brightness down"),
    (r"playerctl next", "Next track"), (r"playerctl previous", "Previous track"),
    (r"playerctl play-pause", "Play / pause"),
    (r"keybinds\.py", "Search all keybinds"), (r"kitty-float", "Floating terminal"),
    (r"keybind-panel\.py", "Keybinds & commands panel"), (r"clipboard-panel", "Clipboard history"),
    (r"wallpaper-picker", "Wallpaper carousel"),
    (r"wallpaper\.py next", "Next wallpaper"), (r"wallpaper\.py prev", "Previous wallpaper"),
]

def describe(lines, i, action):
    """Plain-English description: the comment above the bind, or a known action, or the raw action."""
    for pattern, name in KNOWN:
        m = re.search(pattern, action)
        if m:
            return m.expand(name)
    prev = lines[i - 1].strip() if i > 0 else ""
    if prev.startswith("--") and not prev.startswith("----"):
        text = re.sub(r"\s*\(.*?\)", "", prev.lstrip("- ").strip())
        text = re.sub(r"^[\w+ /<>\[\]-]*?:\s*", "", text) if ":" in text else text
        if text and len(text) < 60 and "=" not in text:
            return text[0].upper() + text[1:]
    for pattern, name in KNOWN:
        m = re.search(pattern, action)
        if m:
            return m.expand(name)
    return action

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Keybinds")
        screen = self.get_screen()
        self.set_visual(screen.get_rgba_visual())
        self.set_app_paintable(True)
        self.css = Gtk.CssProvider()
        self.css.load_from_path(os.path.expanduser("~/.config/theme/panel-style.css"))
        Gtk.StyleContext.add_provider_for_screen(screen, self.css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.set_size_request(480, 620)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "theme-panel")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 60)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.capturing = None
        self.connect("key-press-event", self.on_key)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("panel-box")
        self.add(box)
        self.stack = Gtk.Stack(vexpand=True)
        box.add(Gtk.StackSwitcher(stack=self.stack, halign=Gtk.Align.CENTER))
        keys_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        keys_page.add(Gtk.Label(label="Click a key, then press the new combo", xalign=0))
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.add(self.list)
        keys_page.add(scroll)
        self.stack.add_titled(keys_page, "keys", "Keybinds")
        self.stack.add_titled(self.build_commands(), "cmds", "Commands")
        box.add(self.stack)
        self.status = Gtk.Label(xalign=0, wrap=True)
        box.add(self.status)
        self.refresh()

    def build_commands(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        top = Gtk.Box(spacing=6)
        self.cmd_search = Gtk.SearchEntry(placeholder_text="Search commands…", hexpand=True)
        self.cmd_search.connect("search-changed", lambda _e: self.fill_commands())
        edit = Gtk.Button(label="Edit list")
        edit.connect("clicked", lambda _b: subprocess.Popen(["code", CMDS]))
        top.add(self.cmd_search)
        top.add(edit)
        page.add(top)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.cmd_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.add(self.cmd_list)
        page.add(scroll)
        self.fill_commands()
        return page

    def fill_commands(self):
        for child in self.cmd_list.get_children():
            self.cmd_list.remove(child)
        q = self.cmd_search.get_text().strip().lower()
        try:
            lines = open(CMDS).read().splitlines()
        except Exception:
            lines = []
        section = None
        for line in lines:
            s = line.strip()
            if s.startswith("# ---"):
                section = s.strip("# -")
                continue
            if not s or s.startswith("#") or "|" not in s:
                continue
            desc, cmd = [part.strip() for part in s.split("|", 1)]
            if q and q not in desc.lower() and q not in cmd.lower():
                continue
            if section:
                self.cmd_list.add(Gtk.Label(label=f"<b>{GLib.markup_escape_text(section)}</b>",
                                            use_markup=True, xalign=0, margin_top=6))
                section = None
            row = Gtk.Box(spacing=6, margin=3)
            label = Gtk.Label(label=desc, xalign=0, hexpand=True)
            label.set_tooltip_text(cmd)
            run = Gtk.Button(label="Run")
            run.set_tooltip_text(cmd)
            run.connect("clicked", lambda _b, c=cmd: subprocess.Popen(["kitty", "--hold", "sh", "-c", c]))
            copy = Gtk.Button(label="Copy")
            copy.connect("clicked", self.copy_cmd, cmd)
            row.add(label)
            row.add(run)
            row.add(copy)
            self.cmd_list.add(row)
        self.cmd_list.show_all()

    def copy_cmd(self, _btn, cmd):
        subprocess.run(["wl-copy"], input=cmd, text=True)
        self.status.set_text(f"✓ Copied: {cmd[:70]}")

    def refresh(self):
        for child in self.list.get_children():
            self.list.remove(child)
        self.lines, self.binds = read_binds()
        for i, expr, _, _, action in self.binds:
            row = Gtk.Box(spacing=8, margin=4)
            desc = Gtk.Label(label=describe(self.lines, i, action), xalign=0, hexpand=True, wrap=True, max_width_chars=34)
            desc.set_tooltip_text(action)
            row.add(desc)
            btn = Gtk.Button(label=friendly(pretty(expr)))
            if "key" in expr.replace("mainMod", ""):
                btn.set_sensitive(False)
                btn.set_tooltip_text("Set by a loop in the config. Edit the file to change it.")
            else:
                btn.connect("clicked", self.start_capture, i)
            row.add(btn)
            btn.set_size_request(210, -1)
            row.reorder_child(btn, 0)
            self.list.add(row)
        self.list.show_all()

    def start_capture(self, btn, i):
        if self.capturing:
            return
        self.capturing = i
        btn.set_label("Press keys…  (Esc cancels)")
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)

    def stop_capture(self):
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.capturing = None

    def on_key(self, _w, e):
        name = Gdk.keyval_name(e.keyval) or ""
        if self.capturing is None:
            if name == "Escape":
                self.destroy()
            return False
        if name == "Escape":
            self.stop_capture()
            self.refresh()
            return True
        if name in MODIFIER_KEYS:
            return True
        mods = []
        if e.state & (Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.MOD4_MASK):
            mods.append("SUPER")
        if e.state & Gdk.ModifierType.CONTROL_MASK:
            mods.append("CTRL")
        if e.state & Gdk.ModifierType.SHIFT_MASK:
            mods.append("SHIFT")
        if e.state & Gdk.ModifierType.MOD1_MASK:
            mods.append("ALT")
        key = name.upper() if len(name) == 1 else name
        self.apply(" + ".join(mods + [key]))
        return True

    def apply(self, combo):
        i = self.capturing
        self.stop_capture()
        _, expr, start, end, action = next(b for b in self.binds if b[0] == i)
        taken = [b[4] for b in self.binds if b[0] != i and pretty(b[1]).lower() == combo.lower()]
        if taken:
            self.status.set_text(f"⚠ {combo} is already used by {taken[0][:40]}. Not changed.")
            self.refresh()
            return
        before = errors()
        shutil.copy(CFG, BAK)
        lines = self.lines[:]
        lines[i] = lines[i][:start] + to_expr(combo) + lines[i][end:]
        open(CFG, "w").write("\n".join(lines))
        subprocess.run(["hyprctl", "reload"], capture_output=True)
        if errors() != before:
            shutil.copy(BAK, CFG)
            subprocess.run(["hyprctl", "reload"], capture_output=True)
            self.status.set_text(f"✗ {combo} caused a config error, so your config was restored.")
        else:
            self.status.set_text(f"✓ {action[:40]}:  {friendly(pretty(expr))}  →  {friendly(combo)}")
        self.refresh()

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
if "commands" in sys.argv:
    win.stack.set_visible_child_name("cmds")
Gtk.main()
