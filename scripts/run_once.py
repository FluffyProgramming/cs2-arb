"""One full agent cycle. Run: python -m scripts.run_once [--live] [--send-email]

Without --live (or if holdings.json is missing) it runs on fixtures so you can
see the dashboard immediately. With --live it loads holdings.json and pulls
current listings from CSFloat. Always writes state.json for the dashboard.
Alert-only — never places a trade.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cs2_arb.config import load_settings
from cs2_arb.csfloat_client import CSFloatClient, parse_listing
from cs2_arb.models import Holding
from cs2_arb.signals import AlertState, SignalConfig, evaluate
from cs2_arb.sinks import ConsoleSink, EmailSink
from cs2_arb.state import build_state, write_state

HOLDINGS_FILE = "holdings.json"
STATE_FILE = "state.json"
ALERT_STATE_FILE = "alert_state.json"


def load_holdings(path: str) -> list[Holding]:
    data = json.loads(Path(path).read_text())
    ready, pending = [], []
    for row in data:
        (ready if row.get("float_value") is not None else pending).append(row)
    for row in pending:
        print(f"  skip {row['label']}: float_value not set yet")
    return [Holding(**row) for row in ready]


def fixture_setup():
    from demo.fixtures import (AK_DEF, BLOODSPORT_PAINT, DOPPLER_PAINT,
                               KNIFE_DEF, raw_listings)
    holdings = [
        Holding(label="AK-47 | Bloodsport FT (TyLoo craft proxy)",
                market_hash_name="AK-47 | Bloodsport (Field-Tested)",
                def_index=AK_DEF, paint_index=BLOODSPORT_PAINT, float_value=0.2215,
                quantity=4, cost_basis_cents=2900, reserve_cents=2600),
        Holding(label="Karambit | Doppler FT (Chrome Cannon proxy)",
                market_hash_name="Karambit | Doppler (Field-Tested)",
                def_index=KNIFE_DEF, paint_index=DOPPLER_PAINT, float_value=0.1805,
                quantity=1, cost_basis_cents=64000, reserve_cents=66000),
    ]
    listings = [parse_listing(r) for r in raw_listings()]
    return holdings, listings


def live_setup(settings):
    holdings = load_holdings(HOLDINGS_FILE)
    client = CSFloatClient(api_key=settings.csfloat_api_key)
    listings = []
    for h in holdings:
        listings.extend(client.iter_listings(
            market_hash_name=h.market_hash_name, category=h.category, max_pages=3))
    return holdings, listings


def main() -> None:
    live = "--live" in sys.argv
    send_email = "--send-email" in sys.argv
    settings = load_settings(".env")

    if live and Path(HOLDINGS_FILE).exists():
        holdings, listings = live_setup(settings)
        mode = f"LIVE ({len(listings)} listings from CSFloat)"
    else:
        holdings, listings = fixture_setup()
        mode = "FIXTURES (no --live or no holdings.json)"

    cfg = SignalConfig(divergence_pct=settings.divergence_pct,
                       cooldown_seconds=settings.cooldown_seconds)
    # Persisted across runs so the cooldown actually suppresses repeats when
    # this is scheduled — otherwise every cycle re-emails the same listings.
    state = AlertState.load(ALERT_STATE_FILE)
    signals = evaluate(holdings, listings, cfg, state)
    state.prune(time.time(), cfg.cooldown_seconds * 4)
    state.save()

    print(f"cycle mode: {mode}")
    ConsoleSink().emit(signals)

    write_state(STATE_FILE, build_state(holdings, listings, signals))
    print(f"wrote {STATE_FILE} — open dashboard.html to view")

    if send_email and signals:
        EmailSink(settings).emit(signals)
        print(f"emailed {len(signals)} signal(s) to {settings.mail_to}")


if __name__ == "__main__":
    main()
