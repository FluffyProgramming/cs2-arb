import json

from cs2_arb.config import load_settings
from cs2_arb.csfloat_client import parse_listing
from cs2_arb.models import Holding
from cs2_arb.signals import AlertState, SignalConfig, evaluate_holding
from cs2_arb.sinks import EmailSink, JsonStateSink
from demo.fixtures import AK_DEF, BLOODSPORT_PAINT, raw_listings


def _signals():
    listings = [parse_listing(r) for r in raw_listings()]
    h = Holding(label="AK", market_hash_name="AK-47 | Bloodsport (Field-Tested)",
                def_index=AK_DEF, paint_index=BLOODSPORT_PAINT, float_value=0.2215,
                reserve_cents=2500)
    return evaluate_holding(h, listings, SignalConfig(), AlertState(), now=1000)


def test_env_real_vars_win_over_dotenv(monkeypatch, tmp_path):
    envfile = tmp_path / ".env"
    envfile.write_text("DIVERGENCE_PCT=0.50\nSMTP_HOST=from-dotenv\n")
    monkeypatch.setenv("SMTP_HOST", "from-real-env")  # should win
    s = load_settings(str(envfile))
    assert s.smtp_host == "from-real-env"
    assert s.divergence_pct == 0.50  # picked up from .env
    assert s.email_configured is False  # no user/pass/to


def test_json_state_sink_writes_readable_payload(tmp_path):
    out = tmp_path / "state.json"
    JsonStateSink(str(out)).emit(_signals())
    data = json.loads(out.read_text())
    assert "generated_at" in data and len(data["signals"]) >= 1
    assert data["signals"][0]["kind"] == "reserve_breach"


def test_email_sink_refuses_when_unconfigured():
    s = load_settings("/nonexistent.env")  # nothing set
    sink = EmailSink(s)
    try:
        sink.emit(_signals())
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "not configured" in str(e)


def test_email_body_is_alert_only_and_lists_signals():
    s = load_settings("/nonexistent.env")
    body = EmailSink(s)._body(_signals())
    assert "RESERVE HIT" in body
    assert "no trades were placed" in body
