#!/usr/bin/env bash
# Nightly MTD finder update. Safe to run any time; never deploys or sends anything by itself.
set -u
cd "$(dirname "$0")/.."
mkdir -p logs
LOG="logs/$(date +%F).log"
{
  echo "== $(date '+%F %T %Z') nightly update"
  python3 scripts/update.py
  rc=$?
  echo "exit=$rc"
  # Optional deploy hook (only after Oliver approves hosting): if ./deploy.sh exists and update succeeded, run it.
  if [ $rc -eq 0 ] && [ -x ./deploy.sh ]; then ./deploy.sh; echo "deploy exit=$?"; fi
} >> "$LOG" 2>&1
tail -n 3 "$LOG"
