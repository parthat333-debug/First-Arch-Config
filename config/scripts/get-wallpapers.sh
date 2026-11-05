#!/bin/sh
# Download a random batch of aesthetic wallpapers into ~/Pictures/Wallpapers.
# Usage: get-wallpapers.sh [how-many]   (default 30)
COUNT="${1:-30}"
DEST="$HOME/Pictures/Wallpapers"
TMP="$HOME/.cache/wallpaper-download"

mkdir -p "$DEST"
rm -rf "$TMP"
echo "Downloading the collection (about 570 MB, one-time per run)..."
git clone --depth 1 https://github.com/D3Ext/aesthetic-wallpapers.git "$TMP" || exit 1

added=0
for f in $(find "$TMP" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) | shuf); do
  name=$(basename "$f")
  [ -e "$DEST/$name" ] && continue
  cp "$f" "$DEST/"
  added=$((added + 1))
  [ "$added" -ge "$COUNT" ] && break
done

rm -rf "$TMP"
echo "Added $added new wallpapers to $DEST"
notify-send "Wallpapers" "Added $added new wallpapers. Open Super+W to pick one."
