#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data backups
exec python3 -u bot.py
