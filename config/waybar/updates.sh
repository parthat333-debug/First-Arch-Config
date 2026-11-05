#!/bin/bash
# Waybar update indicator: counts pending official + AUR updates, notifies when the count goes up.
updates=$(checkupdates 2>/dev/null)
repo=$(printf '%s' "$updates" | grep -c .)
aur=$(yay -Qua 2>/dev/null | grep -c .)
n=$((repo + aur))

state=~/.cache/waybar-updates-last
last=$(cat "$state" 2>/dev/null || echo 0)
echo "$n" > "$state"
if [ "$n" -gt "$last" ] && command -v notify-send >/dev/null; then
  msg="$repo official + $aur AUR"
  printf '%s\n' "$updates" | grep -qE '^(linux|linux-firmware|intel-ucode|systemd) ' && msg="$msg (includes kernel/system, reboot after)"
  notify-send -a "Updates" -i system-software-update "$n updates available" "$msg"
fi

if [ "$n" -eq 0 ]; then
  echo '{"text": "\uf00c", "tooltip": "System is up to date", "class": "uptodate"}'
else
  echo "{\"text\": \"\\uf021\\n$n\", \"tooltip\": \"$repo official + $aur AUR updates\\nClick to open\", \"class\": \"pending\"}"
fi
