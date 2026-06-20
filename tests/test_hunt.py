from cs2_arb.hunt import HuntConfig, evaluate_candidate
from cs2_arb.models import Listing, Sticker

MHN = "AK-47 | Redline (Field-Tested)"
DEF, PAINT = 7, 316
CFG = HuntConfig()  # min_margin 0.15, fee 0.02, min_liquidity 8, sticker 0.05


def L(id, price, fv=0.20, stickers=()):
    return Listing(id=id, market_hash_name=MHN, def_index=DEF, paint_index=PAINT,
                   paint_seed=1, float_value=fv, price_cents=price, stickers=stickers)


def comps(n=10, price=2000):
    # n listings, floats tightly around 0.20 (in band), all priced `price`
    return [L(f"c{i}", price, fv=0.198 + i * 0.0005) for i in range(n)]


def test_flip_fires_on_underpriced_base_skin():
    cand = L("cand", 1500, fv=0.20)            # $15 vs $20 fair
    sig = evaluate_candidate(cand, comps(), CFG)
    assert sig is not None and sig.kind == "flip"
    # net = 2000*0.98 - 1500 = 460 -> ROI 0.306
    assert sig.metadata["net_cents"] == 460
    assert round(sig.metadata["roi"], 3) == 0.307
    assert sig.severity == "high"              # >= 2x min_margin


def test_margin_below_threshold_is_skipped():
    cand = L("cand", 1850, fv=0.20)            # only ~6% ROI after fee
    assert evaluate_candidate(cand, comps(), CFG) is None


def test_sticker_heavy_candidate_skipped():
    cand = L("cand", 1500, fv=0.20, stickers=(Sticker("X", 0, 800),))  # 53% stickers
    assert evaluate_candidate(cand, comps(), CFG) is None


def test_illiquid_skin_skipped():
    cand = L("cand", 1500, fv=0.20)
    assert evaluate_candidate(cand, comps(n=3), CFG) is None   # < min_liquidity


def test_stickered_comps_excluded_from_fair_value():
    # comps are stickered (excluded) -> not enough base comps -> no flip
    sticky = [L(f"s{i}", 2000, fv=0.198 + i * 0.0005,
                stickers=(Sticker("X", 0, 1500),)) for i in range(10)]
    assert evaluate_candidate(L("cand", 1500), sticky, CFG) is None


def test_souvenir_candidate_skipped():
    cand = Listing(id="souv", market_hash_name=MHN, def_index=DEF, paint_index=PAINT,
                   paint_seed=1, float_value=0.20, price_cents=1500, is_souvenir=True)
    assert evaluate_candidate(cand, comps(), CFG) is None


def test_candidate_excluded_from_own_comps():
    cand = L("dup", 1500, fv=0.20)
    # pass the candidate inside the comp pool; it must not count toward itself
    pool = comps() + [cand]
    sig = evaluate_candidate(cand, pool, CFG)
    assert sig is not None
    assert sig.fair_value.n_comps == 10        # the 10 real comps, not 11
