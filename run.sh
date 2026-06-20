#!/usr/bin/env bash
# Cron wrapper for the CS2 arb agent (Raspberry Pi / VPS / any cron host).
# Runs one live cycle and emails new signals. Safe to run every 30 min — the
# persisted cooldown (alert_state.json) prevents re-alerting the same listing.
#
# Setup:
#   chmod +x run.sh
#   crontab -e   then add (every 30 min):
#     */30 * * * * /home/pi/cs2_arb_demo/run.sh >> /home/pi/cs2_arb_demo/cron.log 2>&1
#   And refresh the watchlist from your inventory weekly (Mon 04:00):
#     0 4 * * 1 cd /home/pi/cs2_arb_demo && .venv/bin/python -m scripts.build_holdings >> cron.log 2>&1

set -euo pipefail
cd "$(dirname "$0")"

# use the project venv if present, else system python3
PY="python3"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"

echo "----- $(date '+%Y-%m-%d %H:%M:%S') -----"
"$PY" -m scripts.run_once --live --send-email
