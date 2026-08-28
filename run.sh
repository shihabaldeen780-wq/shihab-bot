#!/bin/bash
# Gh_317_bot - شاخوف711 - تطوير واجهة شهاب ومركز المحتوى - commit 21606b7

echo "service: 29418 started"
echo "بوت شهاب - Gh_317_bot جاهز للعمل - @Gh_317_bot"
echo "Application started"
source .env 2>/dev/null || true
python3 bot.py
