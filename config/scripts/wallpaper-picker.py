#!/usr/bin/env python3
# Wallpaper carousel: slanted cards, colour filters, search.
# Keys: Left/Right browse, Enter = this workspace, Shift+Enter = all workspaces, Esc = close.
import colorsys, glob, hashlib, json, math, os, subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, GtkLayerShell

FOLDER = os.path.expanduser("~/Pictures/Wallpapers")
ENGINE = os.path.expanduser("~/.config/scripts/wallpaper.py")
STATE = os.path.expanduser("~/.config/hypr/wallpapers.json")
CACHE = os.path.expanduser("~/.cache/wallpaper-colors.json")
THUMBS = os.path.expanduser("~/.cache/wallpaper-thumbs")
EXTS = (".jpg", ".jpeg", ".png", ".webp")
TW, TH = 420, 300      # size of the centre card
SKEW = 50              # how slanted the cards are
SWATCHES = [("all", None), ("red", "#e74c3c"), ("orange", "#f39c12"), ("yellow", "#f1c40f"),
            ("green", "#2ecc71"), ("blue", "#3498db"), ("purple", "#9b59b6"),
            ("pink", "#e84393"), ("gray", "#a0a0a0")]

def accent():
    try:
        h = json.load(open(os.path.expanduser("~/.config/theme/current.json")))["accent"]
    except Exception:
        h = "#ffffff"
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

def active_ws():
    out = subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True).stdout
    return str(json.loads(out)["id"])

def current_wallpaper():
    try:
        s = json.load(open(STATE))
        return s.get("workspaces", {}).get(active_ws()) or s.get("default", "")
    except Exception:
        return ""

def thumb(path):
    """Load the image cropped to fill a TW x TH card (cached on disk after the first time)."""
    key = hashlib.md5(f"{path}:{os.path.getmtime(path)}:{TW}x{TH}".encode()).hexdigest()
    cached = os.path.join(THUMBS, key + ".png")
    if os.path.exists(cached):
        return GdkPixbuf.Pixbuf.new_from_file(cached)
    _, w, h = GdkPixbuf.Pixbuf.get_file_info(path)
    s = max(TW / w, TH / h)
    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, max(TW, int(w * s) + 1), max(TH, int(h * s) + 1), False)
    sub = pix.new_subpixbuf((pix.get_width() - TW) // 2, (pix.get_height() - TH) // 2, TW, TH)
    os.makedirs(THUMBS, exist_ok=True)
    sub.savev(cached, "png", [], [])
    return sub

def colour_of(pix):
    """Most common saturated hue in the image, or gray if it is mostly unsaturated."""
    small = pix.scale_simple(24, 24, GdkPixbuf.InterpType.BILINEAR)
    data, n, rs = small.get_pixels(), small.get_n_channels(), small.get_rowstride()
    counts, saturated = {}, 0
    for y in range(24):
        for x in range(24):
            i = y * rs + x * n
            h, s, v = colorsys.rgb_to_hsv(data[i] / 255, data[i + 1] / 255, data[i + 2] / 255)
            if s < 0.25 or v < 0.2:
                continue
            saturated += 1
            deg = h * 360
            name = ("red" if deg < 15 or deg >= 345 else "orange" if deg < 45 else "yellow" if deg < 70
                    else "green" if deg < 170 else "blue" if deg < 260 else "purple" if deg < 300 else "pink")
            counts[name] = counts.get(name, 0) + 1
    return "gray" if saturated < 24 * 24 * 0.15 else max(counts, key=counts.get)

class Picker(Gtk.Window):
    def __init__(self):
        super().__init__(title="Wallpapers")
        screen = self.get_screen()
        self.set_visual(screen.get_rgba_visual())
        self.set_app_paintable(True)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "wallpaper-picker")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)

        css = Gtk.CssProvider()
        css.load_from_path(os.path.expanduser("~/.config/theme/panel-style.css"))
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        sw = Gtk.CssProvider()
        sw.load_from_data("".join(
            f".sw-{k} {{ background-color: {c}; min-width: 22px; min-height: 22px; padding: 0; }}\n"
            for k, c in SWATCHES if c).encode() +
            b".swatch.active { box-shadow: inset 0 0 0 2px white; }\n")
        Gtk.StyleContext.add_provider_for_screen(screen, sw, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)

        self.files = sorted(f for f in glob.glob(FOLDER + "/*") if f.lower().endswith(EXTS))
        try:
            self.cache = json.load(open(CACHE))
        except Exception:
            self.cache = {}
        self.thumbs, self.colours = {}, {}
        self.filter, self.query = "all", ""
        self.accent = accent()
        cur = current_wallpaper()
        self.items = list(self.files)
        self.target = self.items.index(cur) if cur in self.items else 0
        self.pos = float(self.target)
        self.order = sorted(range(len(self.files)), key=lambda i: abs(i - self.target))

        overlay = Gtk.Overlay()
        self.add(overlay)
        self.area = Gtk.DrawingArea()
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        self.area.connect("draw", self.draw)
        self.area.connect("button-press-event", self.on_click)
        self.area.connect("scroll-event", self.on_scroll)
        overlay.add(self.area)

        bar = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=70)
        bar.get_style_context().add_class("panel-box")
        self.swatch_btns = {}
        for key, colour in SWATCHES:
            btn = Gtk.Button(label="All" if key == "all" else "")
            btn.get_style_context().add_class("swatch")
            if colour:
                btn.get_style_context().add_class(f"sw-{key}")
            btn.connect("clicked", self.set_filter, key)
            self.swatch_btns[key] = btn
            bar.add(btn)
        self.search = Gtk.SearchEntry(placeholder_text="Search…", width_chars=14)
        self.search.connect("search-changed", self.on_search)
        bar.add(self.search)
        overlay.add_overlay(bar)

        hint = Gtk.Label(label="← →  browse      Enter  this workspace      Shift+Enter  all workspaces      Esc  close",
                         halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=70)
        hint.get_style_context().add_class("panel-box")
        overlay.add_overlay(hint)

        self.connect("key-press-event", self.on_key)
        self.set_filter(None, "all")
        GLib.idle_add(self.load_next, 0)
        GLib.timeout_add(16, self.animate)

    # --- data ---
    def load_next(self, i):
        if i >= len(self.files):
            json.dump(self.cache, open(CACHE, "w"))
            return False
        path = self.files[self.order[i]]
        try:
            pix = thumb(path)
            self.thumbs[path] = Gdk.cairo_surface_create_from_pixbuf(pix, 1, None)
            key = f"{path}:{os.path.getmtime(path)}"
            if key not in self.cache:
                self.cache[key] = colour_of(pix)
            self.colours[path] = self.cache[key]
            if self.filter != "all":
                self.refilter()
            self.area.queue_draw()
        except Exception:
            pass
        GLib.idle_add(self.load_next, i + 1)
        return False

    def refilter(self):
        keep = self.items[self.target] if self.items else None
        self.items = [f for f in self.files
                      if (self.filter == "all" or self.colours.get(f) == self.filter)
                      and self.query in os.path.basename(f).lower()]
        self.target = self.items.index(keep) if keep in self.items else 0
        self.pos = float(self.target)
        self.area.queue_draw()

    def set_filter(self, _btn, key):
        self.filter = key
        for k, b in self.swatch_btns.items():
            (b.get_style_context().add_class if k == key else b.get_style_context().remove_class)("active")
        self.refilter()

    def on_search(self, entry):
        self.query = entry.get_text().strip().lower()
        self.refilter()

    # --- movement ---
    def move(self, step):
        if self.items:
            self.target = max(0, min(len(self.items) - 1, self.target + step))

    def animate(self):
        if abs(self.target - self.pos) > 0.001:
            self.pos += (self.target - self.pos) * 0.2
            self.area.queue_draw()
        return True

    def apply(self, everywhere):
        if not self.items:
            return
        subprocess.Popen([ENGINE, "set", self.items[self.target]] + (["all"] if everywhere else []))
        self.destroy()

    def on_key(self, _w, e):
        name = Gdk.keyval_name(e.keyval)
        if name == "Escape":
            self.destroy()
        elif name in ("Left", "Right"):
            self.move(-1 if name == "Left" else 1)
        elif name in ("Return", "KP_Enter"):
            self.apply(bool(e.state & Gdk.ModifierType.SHIFT_MASK))
        else:
            return False
        return True

    def on_scroll(self, _w, e):
        if e.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            self.move(-1)
        elif e.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            self.move(1)
        return True

    def on_click(self, w, e):
        offset = (e.x - w.get_allocated_width() / 2) / 300
        if abs(offset) < 0.7:
            self.apply(bool(e.state & Gdk.ModifierType.SHIFT_MASK))
        else:
            self.move(round(offset))
        return True

    # --- drawing ---
    def card(self, cr, x, y, cw, ch):
        cr.new_path()
        cr.move_to(x + SKEW, y)
        cr.line_to(x + cw, y)
        cr.line_to(x + cw - SKEW, y + ch)
        cr.line_to(x, y + ch)
        cr.close_path()

    def draw(self, w, cr):
        width, height = w.get_allocated_width(), w.get_allocated_height()
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.paint()
        if not self.items:
            cr.set_source_rgb(1, 1, 1)
            cr.set_font_size(20)
            cr.move_to(width / 2 - 120, height / 2)
            cr.show_text("No wallpapers match")
            return
        cx, cy = width / 2, height / 2
        for i in sorted(range(len(self.items)), key=lambda i: -abs(i - self.pos)):
            d = i - self.pos
            ad = abs(d)
            if ad > 7:
                continue
            t = min(ad, 1)
            ch = TH * (1 - 0.13 * t)
            cw = (TW - t * (TW - 170)) * max(0.75, 1 - 0.05 * max(0, ad - 1))
            x = cx + d * 190 + math.copysign(t * 110, d) - cw / 2
            y = cy - ch / 2
            pix = self.thumbs.get(self.items[i])
            cr.save()
            self.card(cr, x, y, cw, ch)
            cr.clip()
            if pix:
                s = ch / TH
                cr.translate(x + cw / 2 - TW * s / 2, y)
                cr.scale(s, s)
                cr.set_source_surface(pix, 0, 0)
                cr.paint_with_alpha(1.0 if ad < 0.5 else 0.8)
            else:
                cr.set_source_rgba(1, 1, 1, 0.1)
                cr.paint()
            cr.restore()
            if ad < 0.5:
                self.card(cr, x, y, cw, ch)
                cr.set_source_rgb(*self.accent)
                cr.set_line_width(3)
                cr.stroke()

win = Picker()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
