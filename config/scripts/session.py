#!/usr/bin/env python3
# Session: at login, reopen apps on the workspaces they were on; then save what's open every 20 s.
import glob, json, os, re, shlex, subprocess, time

STATE = os.path.expanduser("~/.local/state/hypr-session.json")
SKIP = {"", "hyprland-share-picker"}

def clients():
    out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return []

def desktop_exec(cls):
    """Find the app's launcher command from its .desktop file."""
    cls_l = cls.lower()
    for folder in ("~/.local/share/applications", "/usr/share/applications"):
        for f in glob.glob(os.path.expanduser(folder) + "/*.desktop"):
            try:
                text = open(f).read()
            except Exception:
                continue
            stem = os.path.basename(f)[:-8].lower()
            wm = re.search(r"^StartupWMClass=(.*)$", text, re.M)
            if (wm and wm.group(1).strip().lower() == cls_l) or stem == cls_l or stem.endswith("." + cls_l):
                ex = re.search(r"^Exec=(.*)$", text, re.M)
                if ex:
                    return re.sub(r"\s*%[a-zA-Z]", "", ex.group(1)).strip()
    return None

def cmdline(pid):
    try:
        parts = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
        return " ".join(shlex.quote(p.decode()) for p in parts if p)
    except Exception:
        return None

def save():
    seen, apps = set(), []
    for c in clients():
        cls, pid = c.get("class", ""), c.get("pid")
        ws = (c.get("workspace") or {}).get("id")
        if cls in SKIP or pid in seen or ws is None or ws < 1:
            continue
        seen.add(pid)
        cmd = desktop_exec(cls) or cmdline(pid)
        if cmd:
            apps.append({"class": cls, "workspace": ws, "cmd": cmd})
    if not apps:  # never overwrite a good save with an empty one
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    json.dump(apps, open(tmp, "w"), indent=2)
    os.replace(tmp, STATE)

def restore():
    try:
        apps = json.load(open(STATE))
    except Exception:
        return
    for a in apps:
        lua = f'hl.dsp.exec_cmd({json.dumps(a["cmd"])}, {{ workspace = "{a["workspace"]} silent" }})'
        subprocess.run(["hyprctl", "dispatch", lua], capture_output=True)
        time.sleep(0.5)

# Only one copy at a time
me = str(os.getpid())
others = subprocess.run(["pgrep", "-f", "scripts/session.py"], capture_output=True, text=True).stdout.split()
if any(p != me for p in others):
    raise SystemExit

restore()
time.sleep(30)  # let restored apps open before the first save
while True:
    save()
    time.sleep(20)
