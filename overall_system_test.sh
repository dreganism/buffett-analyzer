#!/usr/bin/env bash
set -euo pipefail
BASE="https://buffett-analyzer.investments"      # e.g., https://buffett-analyzer.investments
APP="$BASE/app"                 # adjust if not using /app
COOKIE_JAR="$(mktemp)"

echo "== HEAD (no follow) =="
curl -s -I "$APP"

echo
echo "== Full redirect chain (max 20) =="
curl -s -I -L --max-redirs 20 -o /dev/null -w '%{url_effective}\n' "$APP"

echo
echo "== Verbose trace with cookies =="
curl -v -I -L "$APP" -c "$COOKIE_JAR" -b "$COOKIE_JAR" --max-redirs 20 2>&1 | sed -nE '/^> |^< |Location:|Set-Cookie:/p'
