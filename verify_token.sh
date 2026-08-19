#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
set -a
source .env
set +a
response="$(curl -fsS "https://api.telegram.org/bot${BOT_TOKEN}/getMe")"
case "$response" in
  *'"ok":true'*)
    echo "TOKEN_OK"
    echo "$response" | sed -E 's/.*"username":"([^"]+)".*/BOT_USERNAME=@\1/'
    ;;
  *)
    echo "TOKEN_INVALID_OR_UNAVAILABLE"
    exit 1
    ;;
esac
