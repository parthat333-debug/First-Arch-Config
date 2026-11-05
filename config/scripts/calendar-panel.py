#!/usr/bin/env python3
# Calendar panel: calendar with per-day tasks, plus world clocks.
import datetime, json, os
from zoneinfo import ZoneInfo, available_timezones
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GLib, GtkLayerShell

DATA = os.path.expanduser("~/.local/share/hypr-panels/calendar.json")
DEFAULT_ZONES = ["Asia/Kolkata", "UTC", "Europe/London", "America/New_York", "Asia/Tokyo"]

def load():
    try:
        d = json.load(open(DATA))
    except Exception:
        d = {}
    d.setdefault("tasks", {})
    d.setdefault("zones", DEFAULT_ZONES[:])
    return d

def save(d):
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    json.dump(d, open(DATA, "w"), indent=2)

def zone_choices():
    """Country/city -> time zone pairs from the system's tzdata files."""
    names, rows = {}, []
    try:
        for line in open("/usr/share/zoneinfo/iso3166.tab"):
            if not line.startswith("#") and "\t" in line:
                code, name = line.rstrip("\n").split("\t")[:2]
                names[code] = name
        for line in open("/usr/share/zoneinfo/zone.tab"):
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                city = parts[2].split("/")[-1].replace("_", " ")
                rows.append((f"{names.get(parts[0], parts[0])} — {city}", parts[2]))
    except Exception:
        pass
    rows.append(("UTC — Universal time", "UTC"))
    return sorted(rows)

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Calendar")
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
        self.data = load()
        self.choices = zone_choices()

        outer = Gtk.Box(spacing=16)
        outer.get_style_context().add_class("panel-box")
        outer.set_size_request(760, 620)
        self.add(outer)

        # Left: calendar + tasks
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        outer.add(left)
        self.cal = Gtk.Calendar()
        self.cal.connect("day-selected", lambda _c: self.show_tasks())
        self.cal.connect("month-changed", lambda _c: self.mark_days())
        self.search_in = Gtk.SearchEntry(placeholder_text="Search all tasks…")
        self.search_in.connect("search-changed", lambda _e: self.search())
        left.add(self.search_in)
        left.add(self.cal)

        self.day_label = Gtk.Label(xalign=0)
        left.add(self.day_label)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.tasks = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.add(self.tasks)
        left.add(scroll)

        form = Gtk.Box(spacing=6)
        self.title_in = Gtk.Entry(placeholder_text="New task", hexpand=True)
        self.time_in = Gtk.Entry(placeholder_text="Time", width_chars=6)
        self.remind_in = Gtk.ComboBoxText()
        for label in ("At time", "10 min before", "1 hour before", "No reminder"):
            self.remind_in.append_text(label)
        self.remind_in.set_active(0)
        add = Gtk.Button(label="Add")
        form.add(self.title_in)
        form.add(self.time_in)
        form.add(self.remind_in)
        form.add(add)
        left.add(form)
        self.details_in = Gtk.Entry(placeholder_text="Details (optional)")
        left.add(self.details_in)
        add.connect("clicked", self.add_task)
        self.title_in.connect("activate", self.add_task)
        self.details_in.connect("activate", self.add_task)

        # Right: world clocks
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right.set_size_request(260, -1)
        outer.add(right)
        right.add(Gtk.Label(label="<b>World clocks</b>", use_markup=True, xalign=0))
        self.clocks = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right.add(self.clocks)
        zone_form = Gtk.Box(spacing=6)
        self.zone_in = Gtk.Entry(placeholder_text="Search a country or city…", hexpand=True)
        self.zone_in.connect("changed", lambda _e: self.search_zones())
        zone_add = Gtk.Button(label="Add")
        zone_form.add(self.zone_in)
        zone_form.add(zone_add)
        right.add(zone_form)
        self.zone_status = Gtk.Label(xalign=0, wrap=True, max_width_chars=30)
        right.add(self.zone_status)
        self.zone_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right.add(self.zone_results)
        zone_add.connect("clicked", self.add_zone)
        self.zone_in.connect("activate", self.add_zone)

        self.build_clocks()
        self.mark_days()
        self.show_tasks()
        GLib.timeout_add_seconds(1, self.tick)

    # --- tasks ---
    def selected(self):
        y, m, d = self.cal.get_date()
        return datetime.date(y, m + 1, d)

    def mark_days(self):
        self.cal.clear_marks()
        y, m, _ = self.cal.get_date()
        for key, items in self.data["tasks"].items():
            day = datetime.date.fromisoformat(key)
            if items and day.year == y and day.month == m + 1:
                self.cal.mark_day(day.day)

    def show_tasks(self):
        day = self.selected()
        self.day_label.set_markup(f"<b>{day.strftime('%A, %d %B %Y')}</b>")
        for child in self.tasks.get_children():
            self.tasks.remove(child)
        items = self.data["tasks"].get(day.isoformat(), [])
        if not items:
            self.tasks.add(Gtk.Label(label="No tasks for this day.", xalign=0))
        for idx, t in enumerate(sorted(items, key=lambda t: t.get("time") or "99")):
            row = Gtk.Box(spacing=8, margin=4)
            check = Gtk.CheckButton(active=t["done"])
            check.connect("toggled", self.toggle_task, day, t)
            bell = " \uf0f3" if t.get("time") and t.get("remind", 0) >= 0 else ""
            text = (f"{t['time']}{bell}  " if t.get("time") else "") + t["title"]
            if t["done"]:
                text = f"<s>{GLib.markup_escape_text(text)}</s>"
            else:
                text = GLib.markup_escape_text(text)
            if t.get("details"):
                text += f"\n<small>{GLib.markup_escape_text(t['details'])}</small>"
            row.add(check)
            row.add(Gtk.Label(label=text, use_markup=True, xalign=0, hexpand=True, wrap=True))
            delete = Gtk.Button(label="\uf00d")
            delete.connect("clicked", self.delete_task, day, t)
            row.add(delete)
            self.tasks.add(row)
        self.tasks.show_all()

    def add_task(self, *_):
        title = self.title_in.get_text().strip()
        if not title:
            return
        day = self.selected().isoformat()
        self.data["tasks"].setdefault(day, []).append({
            "title": title, "time": self.time_in.get_text().strip(),
            "details": self.details_in.get_text().strip(), "done": False,
            "remind": (0, 10, 60, -1)[self.remind_in.get_active()]})
        save(self.data)
        for entry in (self.title_in, self.time_in, self.details_in):
            entry.set_text("")
        self.mark_days()
        self.show_tasks()

    def toggle_task(self, check, day, t):
        t["done"] = check.get_active()
        save(self.data)
        GLib.idle_add(self.show_tasks)

    def delete_task(self, _btn, day, t):
        items = self.data["tasks"][day.isoformat()]
        items.remove(t)
        if not items:
            del self.data["tasks"][day.isoformat()]
        save(self.data)
        self.mark_days()
        self.show_tasks()

    def search(self):
        q = self.search_in.get_text().strip().lower()
        if not q:
            self.show_tasks()
            return
        for child in self.tasks.get_children():
            self.tasks.remove(child)
        hits = [(day, t) for day, items in sorted(self.data["tasks"].items()) for t in items
                if q in t["title"].lower() or q in t.get("details", "").lower()]
        self.day_label.set_markup(f"<b>{len(hits)} result(s) for '{GLib.markup_escape_text(q)}'</b>")
        if not hits:
            self.tasks.add(Gtk.Label(label="Nothing found.", xalign=0))
        for day, t in hits:
            d = datetime.date.fromisoformat(day)
            text = f"{d.strftime('%a %d %b %Y')}   " + (f"{t['time']}  " if t.get("time") else "") + t["title"]
            btn = Gtk.Button(label=text)
            btn.get_child().set_xalign(0)
            btn.connect("clicked", self.jump_to, d)
            self.tasks.add(btn)
        self.tasks.show_all()

    def jump_to(self, _btn, d):
        self.search_in.set_text("")
        self.cal.select_month(d.month - 1, d.year)
        self.cal.select_day(d.day)
        self.show_tasks()

    # --- world clocks ---
    def build_clocks(self):
        for child in self.clocks.get_children():
            self.clocks.remove(child)
        self.clock_labels = []
        for zone in self.data["zones"]:
            row = Gtk.Box(spacing=8)
            name = Gtk.Label(xalign=0, hexpand=True)
            time = Gtk.Label(xalign=1)
            remove = Gtk.Button(label="\uf00d")
            remove.connect("clicked", self.remove_zone, zone)
            row.add(name)
            row.add(time)
            row.add(remove)
            self.clocks.add(row)
            self.clock_labels.append((zone, name, time))
        self.clocks.show_all()
        self.tick()

    def tick(self):
        local = datetime.datetime.now().astimezone()
        for zone, name, time in self.clock_labels:
            now = datetime.datetime.now(ZoneInfo(zone))
            diff = now.date() - local.date()
            day = "" if diff.days == 0 else (" (tomorrow)" if diff.days > 0 else " (yesterday)")
            city = zone.split("/")[-1].replace("_", " ")
            name.set_markup(f"{city}\n<small>{now.strftime('%a %d %b')}{day}</small>")
            time.set_markup(f"<b>{now.strftime('%H:%M:%S')}</b>")
        return True

    def add_zone(self, *_):
        zone = self.zone_in.get_text().strip()
        if zone not in available_timezones():
            matches = sorted(z for z in available_timezones() if zone.lower() in z.lower())[:4]
            hint = f" Did you mean: {', '.join(matches)}?" if matches else ""
            self.zone_status.set_text(f"Unknown time zone '{zone}'.{hint}")
            return
        if zone not in self.data["zones"]:
            self.data["zones"].append(zone)
            save(self.data)
        self.zone_in.set_text("")
        self.zone_status.set_text("")
        self.build_clocks()

    def search_zones(self):
        for child in self.zone_results.get_children():
            self.zone_results.remove(child)
        q = self.zone_in.get_text().strip().lower()
        if len(q) < 2:
            return
        hits = [(label, zone) for label, zone in self.choices if q in label.lower() or q in zone.lower()][:8]
        if not hits:
            self.zone_results.add(Gtk.Label(label="No matches.", xalign=0))
        for label, zone in hits:
            btn = Gtk.Button(label=label)
            btn.get_child().set_xalign(0)
            btn.connect("clicked", self.pick_zone, zone)
            self.zone_results.add(btn)
        self.zone_results.show_all()

    def pick_zone(self, _btn, zone):
        if zone not in self.data["zones"]:
            self.data["zones"].append(zone)
            save(self.data)
        self.zone_in.set_text("")
        self.zone_status.set_text("")
        self.build_clocks()

    def remove_zone(self, _btn, zone):
        self.data["zones"].remove(zone)
        save(self.data)
        self.build_clocks()

win = Panel()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
