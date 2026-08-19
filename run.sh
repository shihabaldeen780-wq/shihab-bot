#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

while true; do
  python3 bot.py
  status=$?
  if [ "$status" -eq 130 ] || [ "$status" -eq 143 ]; then
    exit 0
  fi
  echo "bot exited with status $status; retrying in 5 seconds..." >&2
  sleep 5
done
