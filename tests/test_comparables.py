from cs2_arb.comparables import _percentile, fair_value, find_comps
from cs2_arb.csfloat_client import parse_listing
from cs2_arb.models import Holding
from demo.fixtures import AK_DEF, BLOODSPORT_PAINT, raw_listings


def listings():
    return [parse_listing(r) for r in raw_listings()]


def ak_holding():
    return Holding(
        label="AK test", market_hash_name="AK-47 | Bloodsport (Field-Tested)",
        def_index=AK_DEF, paint_index=BLOODSPORT_PAINT, float_value=0.2215,
    )


def test_comps_exclude_other_skins_and_wear_tiers():
    comps, _ = find_comps(ak_holding(), listings(), band_width=0.02, min_comps=1)
    ids = {c.id for c in comps}
    # the 7 AK Bloodsport FT listings in-band (1001-1007) are included
    assert {"1001", "1002", "1003", "1004", "1005", "1006", "1007"} <= ids
    # FN-tier AK (1008), Redline (1009), and knives excluded
    assert "1008" not in ids and "1009" not in ids
    assert not any(c.id.startswith("2") for c in comps)


def test_band_widens_until_min_comps():
    # start far too tight; engine should widen to gather comps
    comps, width = find_comps(ak_holding(), listings(),
                              band_width=0.0001, max_band_width=0.05, min_comps=5)
    assert len(comps) >= 5
    assert width > 0.0001


def test_fair_value_math():
    fv = fair_value(ak_holding(), listings(), band_width=0.02, min_comps=1)
    # in-band AK prices: 3300,3150,3200,3250,3350,3100,2400 -> median 3200
    assert fv.median_cents == 3200
    assert fv.low_listing.id == "1007"      # the planted deal
    assert fv.low_listing.price_cents == 2400
    assert 0.0 <= fv.float_rank_pct <= 1.0


def test_percentile_interpolation():
    assert _percentile([100], 0.25) == 100
    assert _percentile([100, 200], 0.0) == 100
    assert _percentile([100, 200], 1.0) == 200
    assert _percentile([100, 200, 300, 400], 0.25) == 175


def test_no_comps_returns_empty_fairvalue():
    h = Holding(label="ghost", market_hash_name="Nonexistent",
                def_index=99999, paint_index=99999, float_value=0.2)
    fv = fair_value(h, listings())
    assert fv.n_comps == 0
    assert fv.median_cents is None
    assert not fv.has_comps
