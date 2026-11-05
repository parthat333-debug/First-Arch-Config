#!/bin/bash
# Prints one line of info for a lock screen label. Usage: lockinfo.sh <item>
W=/tmp/lock-weather

weather() {  # cached for 10 minutes so the lock screen doesn't hammer the weather site
  if [ ! -s "$W" ] || [ $(( $(date +%s) - $(stat -c %Y "$W") )) -gt 600 ]; then
    curl -s --max-time 5 'wttr.in/?format=%t|%C|%l' > "$W.tmp" 2>/dev/null &&
      grep -q '|' "$W.tmp" && mv "$W.tmp" "$W"
  fi
  cat "$W" 2>/dev/null
}

case "$1" in
  temp)    t=$(weather | cut -d'|' -f1); echo "${t:---}" ;;
  cond)    w=$(weather)
           if [ -n "$w" ]; then echo "$(echo "$w" | cut -d'|' -f2)  ·  $(echo "$w" | cut -d'|' -f3 | cut -d, -f1)"
           else echo "Weather offline"; fi ;;
  cpu)     printf '\uf2db   CPU     %s%%\n' "$(top -bn1 | awk '/Cpu\(s\)/ {print int(100-$8)}')" ;;
  ram)     printf '\uf538   RAM     %s\n' "$(free -h | awk '/^Mem/ {print $3" / "$2}')" ;;
  heat)    z=$(grep -l x86_pkg_temp /sys/class/thermal/thermal_zone*/type 2>/dev/null | head -1)
           [ -n "$z" ] && printf '\uf2c9   Temp    %s°C\n' "$(( $(cat "${z%type}temp") / 1000 ))" || echo "" ;;
  disk)    printf '\uf0a0   Disk    %s\n' "$(df -h / | awk 'NR==2 {print $3" / "$2}')" ;;
  net)     s=$(nmcli -t -f active,ssid dev wifi | awk -F: '$1=="yes" {print $2}')
           printf '\uf1eb   WiFi    %s\n' "${s:-offline}" ;;
  battery) printf '\uf240  %s%%\n' "$(cat /sys/class/power_supply/BAT*/capacity | head -1)" ;;
  notif)   n=$(swaync-client -c 2>/dev/null); printf '\uf0f3   %s notification(s)\n' "${n:-0}" ;;
  song)    s=$(playerctl metadata --format '{{ title }}' 2>/dev/null); printf '\uf001   %s\n' "${s:-Nothing playing}" ;;
  artist)  playerctl metadata --format '{{ artist }}' 2>/dev/null || echo "" ;;
esac
