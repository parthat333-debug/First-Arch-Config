#!/usr/bin/env python3
# Wallpapers with awww: per-workspace wallpapers, cycling, smooth transitions.
# Usage: wallpaper.py set PATH [all] | next | prev | daemon
import glob, json, os, re, socket, subprocess, sys, time

FOLDER = os.path.expanduser("~/Pictures/Wallpapers")
STATE = os.path.expanduser("~/.config/hypr/wallpapers.json")
HYPRLOCK = os.path.expanduser("~/.config/hypr/hyprlock.conf")
HYPRPAPER = os.path.expanduser("~/.config/hypr/hyprpaper.conf")
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

def files():
    return sorted(f for f in glob.glob(FOLDER + "/*") if f.lower().endswith(EXTS))

def load():
    try:
        s = json.load(open(STATE))
    except Exception:
        s = {}
        try:  # first run: start from the old hyprpaper wallpaper
            m = re.search(r"^\s*path\s*=\s*(.+)$", open(HYPRPAPER).read(), re.M)
            s["default"] = m.group(1).strip() if m else ""
        except Exception:
            pass
    s.setdefault("default", "")
    s.setdefault("workspaces", {})
    return s

def save(s):
    json.dump(s, open(STATE, "w"), indent=2)

def active_ws():
    out = subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True).stdout
    return str(json.loads(out)["id"])

def wallpaper_for(s, ws):
    return s["workspaces"].get(ws) or s["default"] or (files() or [""])[0]

def show(path, pos="center"):
    if not path:
        return
    subprocess.run(["awww", "img", path, "--transition-type", "grow", "--transition-pos", pos,
                    "--transition-duration", "0.7", "--transition-fps", "60"], capture_output=True)
    if os.path.exists(HYPRLOCK):
        text = open(HYPRLOCK).read()
        text = re.sub(r"^(\s*path\s*=\s*).+$", lambda m: m.group(1) + path, text, count=1, flags=re.M)
        open(HYPRLOCK, "w").write(text)

cmd = sys.argv[1] if len(sys.argv) > 1 else "daemon"

if cmd == "set":
    path, s = sys.argv[2], load()
    if len(sys.argv) > 3 and sys.argv[3] == "all":
        s["default"], s["workspaces"] = path, {}
    else:
        s["workspaces"][active_ws()] = path
    save(s)
    show(path)

elif cmd in ("next", "prev"):
    s, ws, fs = load(), active_ws(), files()
    if fs:
        cur = wallpaper_for(s, ws)
        i = fs.index(cur) if cur in fs else -1
        path = fs[(i + (1 if cmd == "next" else -1)) % len(fs)]
        s["workspaces"][ws] = path
        save(s)
        show(path, "right" if cmd == "next" else "left")

elif cmd == "daemon":
    sock_path = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"
    time.sleep(1)  # give awww-daemon a moment to start
    last = wallpaper_for(load(), active_ws())
    show(last)
    while True:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            buf = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.startswith(b"workspacev2>>"):
                        ws = line.split(b">>", 1)[1].split(b",")[0].decode()
                        path = wallpaper_for(load(), ws)
                        if path != last:
                            show(path)
                            last = path
        except Exception:
            time.sleep(2)
