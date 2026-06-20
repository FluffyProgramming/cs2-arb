"""Hunt for flips on skins you don't own. Run: python -m scripts.run_hunt [--send-email]

Scans CSFloat for underpriced listings ($20-$200 by default), confirms each
against float-band fair value, and alerts on those clearing the ROI threshold.
Writes hunt_state.json for the dashboard. Alert-only — never buys.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cs2_arb.config import load_settings
from cs2_arb.csfloat_client import CSFloatClient
from cs2_arb.hunt import HuntConfig, find_flips
from cs2_arb.signals import AlertState
from cs2_arb.sinks import ConsoleSink, EmailSink
from cs2_arb.state import serialise_signals

TARGETS_FILE = "hunt_targets.json"
HUNT_STATE_FILE = "hunt_state.json"
HUNT_ALERT_STATE = "hunt_alert_state.json"


def main() -> None:
    send_email = "--send-email" in sys.argv
    s = load_settings(".env")
    cfg = HuntConfig(
        min_price_cents=s.hunt_min_price_cents,
        max_price_cents=s.hunt_max_price_cents,
        min_margin=s.hunt_min_margin,
        sell_fee=s.hunt_sell_fee,
        min_liquidity_comps=s.hunt_min_liquidity,
        max_candidates=s.hunt_max_candidates,
        cooldown_seconds=s.cooldown_seconds,
    )
    targets = []
    if Path(TARGETS_FILE).exists():
        targets = json.loads(Path(TARGETS_FILE).read_text())

    client = CSFloatClient(api_key=s.csfloat_api_key, min_interval=1.0)
    state = AlertState.load(HUNT_ALERT_STATE)
    flips = find_flips(client, cfg, targets=targets, state=state)
    state.prune(time.time(), cfg.cooldown_seconds * 4)
    state.save()

    print(f"hunt: ${cfg.min_price_cents/100:.0f}-${cfg.max_price_cents/100:.0f}, "
          f">={cfg.min_margin:.0%} ROI, {len(targets)} curated target(s)")
    ConsoleSink().emit(flips)

    Path(HUNT_STATE_FILE).write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(flips),
        "flips": serialise_signals(flips),
    }, indent=2))
    print(f"wrote {HUNT_STATE_FILE}")

    if send_email and flips:
        EmailSink(s).emit(flips)
        print(f"emailed {len(flips)} flip(s) to {s.mail_to}")


if __name__ == "__main__":
    main()
