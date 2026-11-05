#!/bin/bash
# Waybar RAM meter: 10 dots (2 rows of 5), coloured from the theme panel.
read -r p used total < <(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2}
  END{printf "%d %.1f %.1f", (t-a)*100/t, (t-a)/1048576, t/1048576}' /proc/meminfo)
c=~/.config/theme/current.json
on=$(jq -r .ws_fg "$c"); off=$(jq -r .muted "$c")
[ "$p" -ge 85 ] && on=$(jq -r .danger "$c")
n=$(( (p + 5) / 10 ))
row() { for i in $(seq "$1" "$2"); do
  [ "$i" -le "$n" ] && printf "<span color='%s'>●</span>" "$on" || printf "<span color='%s'>●</span>" "$off"; done; }
echo "{\"text\": \"$(row 1 5)\\n$(row 6 10)\\n$p%\", \"tooltip\": \"RAM $used / $total GB\"}"
