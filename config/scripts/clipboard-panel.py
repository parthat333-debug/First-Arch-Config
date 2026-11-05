#!/usr/bin/env python3
# Clipboard panel: search past copies, click to copy again, delete or clear.
import os, subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GtkLayerShell

def history():
    out = subprocess.run(["cliphist", "list"], capture_output=True, text=True).stdout
    return [line.split("\t", 1) for line in out.splitlines() if "\t" in line]

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Clipboard")
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
        box.set_size_request(460, 560)
        self.add(box)

        top = Gtk.Box(spacing=6)
        top.add(Gtk.Label(label="<b>Clipboard</b>", use_markup=True, xalign=0, hexpand=True))
        clear = Gtk.Button(label="Clear all")
        clear.connect("clicked", self.clear_all)
        top.add(clear)
        box.add(top)

        self.search = Gtk.SearchEntry(placeholder_text="Search copied items…")
        self.search.connect("search-changed", lambda _e: self.fill())
        box.add(self.search)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.add(self.list)
        box.add(scroll)
        self.status = Gtk.Label(label="Click an item to copy it, then paste with Ctrl+V.",
                                xalign=0, wrap=True)
        box.add(self.status)
        self.fill()

    def fill(self):
        for child in self.list.get_children():
            self.list.remove(child)
        q = self.search.get_text().strip().lower()
        items = [(i, text) for i, text in history() if q in text.lower()]
        if not items:
            self.list.add(Gtk.Label(label="Nothing here yet. Copy something!" if not q else "No matches.",
                                    xalign=0))
        for entry_id, text in items[:200]:
            row = Gtk.Box(spacing=6, margin=3)
            label = text.replace("\n", " ⏎ ").strip()
            btn = Gtk.Button(label=label[:60] + ("…" if len(label) > 60 else ""), hexpand=True)
            btn.get_child().set_xalign(0)
            btn.set_tooltip_text(text[:500])
            btn.connect("clicked", self.copy, entry_id, text)
            delete = Gtk.Button(label="\uf00d")
            delete.connect("clicked", self.delete, entry_id, text)
            row.add(btn)
            row.add(delete)
            self.list.add(row)
        self.list.show_all()

    def copy(self, _btn, entry_id, text):
        line = f"{entry_id}\t{text}"
        data = subprocess.run(["cliphist", "decode"], input=line.encode(), capture_output=True).stdout
        subprocess.run(["wl-copy"], input=data)
        self.destroy()

    def delete(self, _btn, entry_id, text):
        subprocess.run(["cliphist", "delete"], input=f"{entry_id}\t{text}".encode())
        self.fill()

    def clear_all(self, _btn):
        subprocess.run(["cliphist", "wipe"])
        self.fill()
        self.status.set_text("✓ Clipboard history cleared.")

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
