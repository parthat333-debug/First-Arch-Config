#!/bin/sh
id=$(hyprctl activeworkspace -j | grep -m1 '"id"' | grep -o '[0-9]*')
if [ "$id" = "$1" ]; then
  echo "{\"text\":\"$1\",\"class\":\"active\"}"
else
  echo "{\"text\":\"$1\"}"
fi
