from cs2_arb.csfloat_client import parse_listing
from cs2_arb.models import Holding
from cs2_arb.signals import AlertState, SignalConfig, evaluate_holding
from demo.fixtures import AK_DEF, BLOODSPORT_PAINT, raw_listings


def listings():
    return [parse_listing(r) for r in raw_listings()]


def holding(reserve=2600):
    return Holding(
        label="AK", market_hash_name="AK-47 | Bloodsport (Field-Tested)",
        def_index=AK_DEF, paint_index=BLOODSPORT_PAINT, float_value=0.2215,
        cost_basis_cents=2900, reserve_cents=reserve,
    )


def test_undervalued_signal_fires_on_planted_deal():
    sigs = evaluate_holding(holding(reserve=1), listings(),
                            SignalConfig(divergence_pct=0.10), AlertState(), now=1000)
    kinds = {s.kind for s in sigs}
    assert "undervalued" in kinds
    deal = next(s for s in sigs if s.kind == "undervalued")
    assert deal.listing.id == "1007"
    assert deal.metadata["discount"] >= 0.10


def test_reserve_breach_fires_and_takes_priority():
    # reserve 2500 -> listing 1007 (2400) breaches it
    sigs = evaluate_holding(holding(reserve=2500), listings(),
                            SignalConfig(), AlertState(), now=1000)
    # 1007 should appear once, as a reserve_breach (not double-counted)
    s1007 = [s for s in sigs if s.listing.id == "1007"]
    assert len(s1007) == 1
    assert s1007[0].kind == "reserve_breach"


def test_reserve_breach_does_not_releak_as_undervalued():
    # Regression: a listing that breaches reserve then sits on cooldown must NOT
    # re-fire as an "undervalued" alert on the next pass.
    state = AlertState()
    cfg = SignalConfig(divergence_pct=0.10, cooldown_seconds=3600)
    first = evaluate_holding(holding(reserve=2500), listings(), cfg, state, now=1000)
    second = evaluate_holding(holding(reserve=2500), listings(), cfg, state, now=1100)
    assert any(s.listing.id == "1007" and s.kind == "reserve_breach" for s in first)
    assert second == []          # no cross-kind re-fire within cooldown


def test_persisted_state_prevents_flood_across_runs(tmp_path):
    # Simulates scheduled runs: each "run" loads state from disk, evaluates,
    # saves. The same listing must NOT re-alert on the next run within cooldown.
    p = str(tmp_path / "alert_state.json")
    cfg = SignalConfig(divergence_pct=0.10, cooldown_seconds=3600)

    s1 = AlertState.load(p)
    first = evaluate_holding(holding(reserve=1), listings(), cfg, s1, now=1000)
    s1.save()
    assert len(first) >= 1

    s2 = AlertState.load(p)  # fresh process, reloads memory from disk
    second = evaluate_holding(holding(reserve=1), listings(), cfg, s2, now=1300)
    assert second == []      # cooldown survived the restart -> no flood

    s3 = AlertState.load(p)
    later = evaluate_holding(holding(reserve=1), listings(), cfg, s3, now=1000 + 4000)
    assert len(later) >= 1   # after cooldown elapses, re-fires


def test_prune_drops_old_entries():
    st = AlertState(_fired={"a": 100.0, "b": 900.0})
    st.prune(now=1000.0, max_age=200.0)  # keep entries newer than 800
    assert "a" not in st._fired and "b" in st._fired


def test_cooldown_dedupes_second_pass():
    state = AlertState()
    cfg = SignalConfig(divergence_pct=0.10, cooldown_seconds=3600)
    first = evaluate_holding(holding(reserve=1), listings(), cfg, state, now=1000)
    second = evaluate_holding(holding(reserve=1), listings(), cfg, state, now=1500)
    assert len(first) >= 1
    assert len(second) == 0          # within cooldown
    third = evaluate_holding(holding(reserve=1), listings(), cfg, state, now=1000 + 4000)
    assert len(third) >= 1           # cooldown elapsed -> re-fires
