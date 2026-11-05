#!/usr/bin/env python3
# Login screen (SDDM): copy the current wallpaper and theme colours into the 'parth' style.
# Usage: login-theme.py [left|center|right]
import json, os, re, subprocess, sys

THEME_DIR = "/usr/share/sddm/themes/sddm-astronaut-theme"
CONF = f"{THEME_DIR}/Themes/parth.conf"
HOME = os.path.expanduser("~")

c = json.load(open(f"{HOME}/.config/theme/current.json"))
try:
    wp = json.load(open(f"{HOME}/.config/hypr/wallpapers.json"))
except Exception:
    wp = {}
wall = wp.get("workspaces", {}).get("1") or wp.get("default")

values = {
    "Font": "JetBrainsMono Nerd Font", "FontSize": "13", "RoundCorners": "14",
    "HourFormat": "HH:mm", "DateFormat": "dddd, d MMMM", "HeaderText": "",
    "DimBackground": "0.25", "DimBackgroundColor": c["bg"],
    "PartialBlur": "false", "Blur": "2.0", "BlurMax": "48", "HaveFormBackground": "false",
    "HeaderTextColor": c["fg"], "DateTextColor": c["fg"], "TimeTextColor": c["fg"],
    "FormBackgroundColor": c["panel_bg"], "BackgroundColor": c["bg"],
    "LoginFieldBackgroundColor": c["panel_bg"], "PasswordFieldBackgroundColor": c["panel_bg"],
    "LoginFieldTextColor": c["fg"], "PasswordFieldTextColor": c["fg"],
    "UserIconColor": c["accent"], "PasswordIconColor": c["accent"],
    "PlaceholderTextColor": c["muted"], "WarningColor": c["danger"],
    "LoginButtonTextColor": c["bg"], "LoginButtonBackgroundColor": c["accent"],
    "SystemButtonsIconsColor": c["fg"], "SessionButtonTextColor": c["fg"],
    "VirtualKeyboardButtonTextColor": c["fg"],
    "DropdownTextColor": c["fg"], "DropdownBackgroundColor": c["panel_bg"],
    "DropdownSelectedBackgroundColor": c["ws_active"],
    "HighlightTextColor": c["fg"], "HighlightBackgroundColor": c["ws_active"],
    "HighlightBorderColor": c["ws_active"],
    "HoverUserIconColor": c["ws_active"], "HoverPasswordIconColor": c["ws_active"],
    "HoverSystemButtonsIconsColor": c["ws_active"], "HoverSessionButtonTextColor": c["ws_active"],
    "HoverVirtualKeyboardButtonTextColor": c["ws_active"],
    "HideVirtualKeyboard": "true", "FormPosition": "center",
}
if len(sys.argv) > 1 and sys.argv[1] in ("left", "center", "right"):
    values["FormPosition"] = sys.argv[1]

if wall and os.path.exists(wall):
    dest = "Backgrounds/parth" + (os.path.splitext(wall)[1].lower() or ".jpg")
    subprocess.run(["sudo", "install", "-m", "644", wall, f"{THEME_DIR}/{dest}"], check=True)
    values["Background"] = dest

text = open(CONF).read()
for key, val in values.items():
    text = re.sub(rf"^{key}=.*$", lambda m, k=key, v=val: f'{k}="{v}"', text, flags=re.M)
subprocess.run(["sudo", "tee", CONF], input=text, text=True, stdout=subprocess.DEVNULL, check=True)
subprocess.run(["sudo", "sed", "-i", "s|^ConfigFile=.*|ConfigFile=Themes/parth.conf|",
                f"{THEME_DIR}/metadata.desktop"], check=True)
print(f"Login screen updated (wallpaper: {os.path.basename(wall) if wall else 'unchanged'}, "
      f"layout: {values['FormPosition']})")
