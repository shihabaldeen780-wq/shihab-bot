#!/bin/bash
# التحقق من توكن Gh_317_bot
if [ -z "$BOT_TOKEN" ]; then
  echo "BOT_TOKEN غير موجود! ضعه في Environment Variables"
  exit 1
fi
curl -s "https://api.telegram.org/bot$BOT_TOKEN/getMe" | grep -q '"ok":true' && echo "Token صحيح - @Gh_317_bot جاهز" || echo "Token خطأ"
