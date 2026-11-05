#!/usr/bin/env python3
# Keeps hypridle in sync with ~/.config/hypr/idle.json and whether the charger is plugged in.
import glob, json, os, subprocess, time

SETTINGS = os.path.expanduser("~/.config/hypr/idle.json")
CONF = os.path.expanduser("~/.config/hypr/hypridle.conf")
DEFAULTS = {"ac": {"dim": 10, "lock": 15, "off": 30},
            "battery": {"dim": 4, "lock": 5, "off": 10},
            "awake": False}
AC = (glob.glob("/sys/class/power_supply/AC*/online") or [None])[0]

def settings():
    try:
        s = json.load(open(SETTINGS))
    except Exception:
        s = {}
    return {**DEFAULTS, **s}

def plugged():
    try:
        return open(AC).read().strip() == "1"
    except Exception:
        return True

def write_conf(t):
    parts = ["general {\n"
             "    lock_cmd = pidof hyprlock || hyprlock\n"
             "    before_sleep_cmd = loginctl lock-session\n"
             "    after_sleep_cmd = hyprctl dispatch 'hl.dsp.dpms(\"on\")'\n}\n"]
    if t["dim"]:
        parts.append(f"listener {{\n    timeout = {t['dim'] * 60}\n"
                     "    on-timeout = brightnessctl -s set 10%\n    on-resume = brightnessctl -r\n}\n")
    if t["lock"]:
        parts.append(f"listener {{\n    timeout = {t['lock'] * 60}\n"
                     "    on-timeout = loginctl lock-session\n}\n")
    if t["off"]:
        parts.append(f"listener {{\n    timeout = {t['off'] * 60}\n"
                     "    on-timeout = hyprctl dispatch 'hl.dsp.dpms(\"off\")'\n"
                     "    on-resume = hyprctl dispatch 'hl.dsp.dpms(\"on\")'\n}\n")
    open(CONF, "w").write("\n".join(parts))

last = None
while True:
    s, ac = settings(), plugged()
    state = (json.dumps(s, sort_keys=True), ac)
    if state != last:
        last = state
        subprocess.run(["pkill", "-x", "hypridle"])
        if not s["awake"]:
            write_conf(s["ac" if ac else "battery"])
            subprocess.Popen(["hypridle"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(5)
