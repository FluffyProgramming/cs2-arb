from cs2_arb.wear import float_rank_pct, wear_tier


def test_wear_tier_boundaries():
    assert wear_tier(0.00) == "Factory New"
    assert wear_tier(0.0699) == "Factory New"
    assert wear_tier(0.07) == "Minimal Wear"
    assert wear_tier(0.15) == "Field-Tested"
    assert wear_tier(0.3799) == "Field-Tested"
    assert wear_tier(0.38) == "Well-Worn"
    assert wear_tier(0.45) == "Battle-Scarred"
    assert wear_tier(1.0) == "Battle-Scarred"


def test_float_rank_pct():
    comps = [0.10, 0.20, 0.30, 0.40]
    assert float_rank_pct(0.05, comps) == 0.0       # lowest -> best
    assert float_rank_pct(0.25, comps) == 0.5
    assert float_rank_pct(0.99, comps) == 1.0       # highest -> worst
    assert float_rank_pct(0.25, []) == 0.0          # no comps
