#!/usr/bin/env python3
# Power panel: switch power profiles and watch real hardware values change.
import glob, json, os, subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GLib, GtkLayerShell

CPU = "/sys/devices/system/cpu"
BAT = (glob.glob("/sys/class/power_supply/BAT*") or [None])[0]
MODES = [("performance", "Performance"), ("balanced", "Balanced"), ("power-saver", "Battery saver")]
TUNABLES = ["Max CPU speed", "Turbo boost", "CPU energy pref", "Asus firmware"]

def read(path):
    try:
        return open(path).read().strip()
    except Exception:
        return None

def num(path):
    v = read(path)
    return int(v) if v and v.lstrip("-").isdigit() else None

def cpu_temp():
    for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
        if read(zone + "/type") == "x86_pkg_temp":
            t = num(zone + "/temp")
            return f"{t / 1000:.0f} °C" if t else "?"
    return "?"

def snapshot():
    s = {}
    if BAT:
        power, energy = num(BAT + "/power_now"), num(BAT + "/energy_now")
        full, status = num(BAT + "/energy_full"), read(BAT + "/status") or "?"
        s["Battery"] = f"{status}, {energy * 100 // full}%" if energy and full else status
        s["Power draw"] = f"{power / 1e6:.1f} W" if power is not None else "?"
        if status == "Discharging" and power and energy:
            hours = energy / power
            s["Time left"] = f"{int(hours)}h {int(hours * 60) % 60:02d}m"
        else:
            s["Time left"] = "—"
    freqs = [f for f in (num(p) for p in glob.glob(CPU + "/cpu[0-9]*/cpufreq/scaling_cur_freq")) if f]
    s["CPU speed now"] = f"{sum(freqs) / len(freqs) / 1e6:.2f} GHz avg" if freqs else "?"
    mx = num(CPU + "/cpu0/cpufreq/scaling_max_freq")
    s["Max CPU speed"] = f"{mx / 1e6:.1f} GHz" if mx else "?"
    s["Turbo boost"] = {"1": "off", "0": "on"}.get(read(CPU + "/intel_pstate/no_turbo"), "?")
    s["CPU energy pref"] = read(CPU + "/cpu0/cpufreq/energy_performance_preference") or "?"
    s["Asus firmware"] = read("/sys/firmware/acpi/platform_profile") or "?"
    s["CPU temp"] = cpu_temp()
    return s

def current_profile():
    return subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True).stdout.strip()

IDLE = os.path.expanduser("~/.config/hypr/idle.json")
IDLE_DEFAULTS = {"ac": {"dim": 10, "lock": 15, "off": 30},
                 "battery": {"dim": 4, "lock": 5, "off": 10}, "awake": False}
AC = (glob.glob("/sys/class/power_supply/AC*/online") or [None])[0]

def load_idle():
    try:
        return {**IDLE_DEFAULTS, **json.load(open(IDLE))}
    except Exception:
        return json.loads(json.dumps(IDLE_DEFAULTS))

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Power")
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

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.get_style_context().add_class("panel-box")
        box.set_size_request(380, -1)
        self.add(box)
        box.add(Gtk.Label(label="<b>Power mode</b>", use_markup=True, xalign=0))

        modes = Gtk.Box(spacing=6, homogeneous=True)
        self.mode_buttons = {}
        for key, label in MODES:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.set_mode, key)
            self.mode_buttons[key] = btn
            modes.add(btn)
        box.add(modes)

        box.add(Gtk.Label(label="<b>Live readings</b>  (from the kernel, every 2 s)", use_markup=True, xalign=0))
        grid = Gtk.Grid(column_spacing=16, row_spacing=4)
        box.add(grid)
        self.values = {}
        for row, name in enumerate(snapshot()):
            grid.attach(Gtk.Label(label=name, xalign=0), 0, row, 1, 1)
            self.values[name] = Gtk.Label(xalign=0)
            grid.attach(self.values[name], 1, row, 1, 1)

        box.add(Gtk.Label(label="<b>Screen &amp; lock timers</b>  (minutes, 0 = never)",
                          use_markup=True, xalign=0))
        self.idle = load_idle()
        tgrid = Gtk.Grid(column_spacing=12, row_spacing=4)
        tgrid.attach(Gtk.Label(label="Plugged in"), 1, 0, 1, 1)
        tgrid.attach(Gtk.Label(label="On battery"), 2, 0, 1, 1)
        for row, (k, label) in enumerate([("dim", "Dim screen"), ("lock", "Lock"), ("off", "Screen off")], 1):
            tgrid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            for col, source in enumerate(["ac", "battery"], 1):
                spin = Gtk.SpinButton.new_with_range(0, 240, 1)
                spin.set_value(self.idle[source][k])
                spin.connect("value-changed", self.on_idle, source, k)
                tgrid.attach(spin, col, row, 1, 1)
        box.add(tgrid)
        awake_row = Gtk.Box(spacing=8)
        awake_row.add(Gtk.Label(label="Keep awake (never dim, lock or turn off)", xalign=0, hexpand=True))
        awake = Gtk.Switch(active=self.idle["awake"])
        awake.connect("notify::active", self.on_awake)
        awake_row.add(awake)
        box.add(awake_row)
        self.idle_status = Gtk.Label(xalign=0)
        box.add(self.idle_status)

        self.changes = Gtk.Label(xalign=0, wrap=True, max_width_chars=48)
        box.add(self.changes)
        self.refresh()
        GLib.timeout_add_seconds(2, self.refresh)

    def refresh(self):
        for name, value in snapshot().items():
            if name in self.values:
                self.values[name].set_text(value)
        try:
            on_ac = open(AC).read().strip() == "1"
        except Exception:
            on_ac = True
        src_name = "plugged in" if on_ac else "on battery"
        self.idle_status.set_text("Keep awake is ON: no dim, lock or screen off." if self.idle["awake"]
                                  else f"Now {src_name}: using the '{'Plugged in' if on_ac else 'On battery'}' timers.")
        active = current_profile()
        for key, btn in self.mode_buttons.items():
            ctx = btn.get_style_context()
            (ctx.add_class if key == active else ctx.remove_class)("active")
        return True

    def save_idle(self):
        json.dump(self.idle, open(IDLE, "w"), indent=2)
        self.refresh()

    def on_idle(self, spin, source, k):
        self.idle[source][k] = int(spin.get_value())
        self.save_idle()

    def on_awake(self, switch, _param):
        self.idle["awake"] = switch.get_active()
        self.save_idle()

    def set_mode(self, _btn, key):
        before = snapshot()
        result = subprocess.run(["powerprofilesctl", "set", key], capture_output=True, text=True)
        if result.returncode != 0:
            self.changes.set_text(f"✗ Couldn't switch: {result.stderr.strip()[:120]}")
            return
        self.changes.set_text("Switching… measuring changes")
        GLib.timeout_add(1500, self.show_changes, before)

    def show_changes(self, before):
        after = snapshot()
        diffs = [f"• {k}: {before[k]} → {after[k]}" for k in TUNABLES if before[k] != after[k]]
        self.changes.set_markup("<b>What changed in the system:</b>\n" + "\n".join(diffs)
                                if diffs else "No hardware settings changed (already in that mode).")
        self.refresh()
        return False

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
