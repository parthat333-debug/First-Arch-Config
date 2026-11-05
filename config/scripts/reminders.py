#!/usr/bin/env python3
# Calendar reminders: notifies for tasks in calendar.json, even when the panel is closed.
import datetime, json, os, re, subprocess, time

DATA = os.path.expanduser("~/.local/share/hypr-panels/calendar.json")
SENT = os.path.expanduser("~/.local/share/hypr-panels/reminders-sent.json")
LATE = datetime.timedelta(minutes=15)  # still fire if we woke up within 15 min of the due time

def parse_time(s):
    m = re.match(r"^\s*(\d{1,2})(?:[:.](\d{2}))?\s*([ap])?\.?\s*m?\.?\s*$", (s or "").lower())
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "p" and h < 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return datetime.time(h, mi) if h < 24 and mi < 60 else None

def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default

while True:
    now = datetime.datetime.now()
    tasks = load(DATA, {}).get("tasks", {})
    sent = set(load(SENT, []))
    for day in (now.date(), now.date() + datetime.timedelta(days=1)):
        for t in tasks.get(day.isoformat(), []):
            at, before = parse_time(t.get("time")), t.get("remind", 0)
            if t.get("done") or at is None or before < 0:
                continue
            due = datetime.datetime.combine(day, at) - datetime.timedelta(minutes=before)
            key = f"{day}|{t['title']}|{t.get('time')}|{before}"
            if due <= now <= due + LATE and key not in sent:
                when = "now" if before == 0 else f"in {before} min" if before < 60 else f"in {before // 60} h"
                body = f"{t.get('time')} · {when}" + (f"\n{t['details']}" if t.get("details") else "")
                subprocess.run(["notify-send", "-a", "Calendar", "-u", "critical", "-i", "x-office-calendar",
                                t["title"], body])
                sent.add(key)
    today = now.date().isoformat()
    sent = {k for k in sent if k.split("|")[0] >= today}
    os.makedirs(os.path.dirname(SENT), exist_ok=True)
    json.dump(sorted(sent), open(SENT, "w"))
    time.sleep(30)
