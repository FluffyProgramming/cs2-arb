"""Fixture listings shaped exactly like the CSFloat /v1/listings response.

These feed the demo and tests so the engine runs without an API key. Two skins:
AK-47 | Bloodsport (FT) and Karambit | Doppler proxy. A couple of listings are
deliberately underpriced to trigger alerts.

def_index / paint_index values here are illustrative placeholders for the demo.
Replace with real schema indices when wiring live holdings.
"""

from __future__ import annotations

# Illustrative indices (placeholders for the demo)
AK_DEF, BLOODSPORT_PAINT = 7, 282
KNIFE_DEF, DOPPLER_PAINT = 507, 417


def _raw(id, mhn, def_index, paint_index, seed, fv, price_cents,
         stattrak=False, stickers=None):
    return {
        "id": id,
        "type": "buy_now",
        "price": price_cents,
        "item": {
            "def_index": def_index,
            "paint_index": paint_index,
            "paint_seed": seed,
            "float_value": fv,
            "is_stattrak": stattrak,
            "is_souvenir": False,
            "market_hash_name": mhn,
            "wear_name": "Field-Tested",
            "stickers": stickers or [],
        },
    }


def raw_listings() -> list[dict]:
    AK = "AK-47 | Bloodsport (Field-Tested)"
    rows = [
        # AK Bloodsport FT comps clustered around float 0.22, fair ~ $32
        _raw("1001", AK, AK_DEF, BLOODSPORT_PAINT, 100, 0.2180, 3300),
        _raw("1002", AK, AK_DEF, BLOODSPORT_PAINT, 200, 0.2205, 3150),
        _raw("1003", AK, AK_DEF, BLOODSPORT_PAINT, 300, 0.2225, 3200),
        _raw("1004", AK, AK_DEF, BLOODSPORT_PAINT, 400, 0.2240, 3250),
        _raw("1005", AK, AK_DEF, BLOODSPORT_PAINT, 500, 0.2190, 3350),
        _raw("1006", AK, AK_DEF, BLOODSPORT_PAINT, 600, 0.2300, 3100),
        # --- planted deal: same float band, ~25% under fair value ---
        _raw("1007", AK, AK_DEF, BLOODSPORT_PAINT, 700, 0.2215, 2400),
        # out of band (different wear tier) — must be ignored
        _raw("1008", AK, AK_DEF, BLOODSPORT_PAINT, 800, 0.0500, 6000),
        # different skin entirely — must be ignored
        _raw("1009", "AK-47 | Redline (Field-Tested)", AK_DEF, 999, 1, 0.2200, 1500),

        # Karambit Doppler comps around float 0.18, fair ~ $700
        _raw("2001", "Karambit | Doppler (Field-Tested)", KNIFE_DEF, DOPPLER_PAINT, 11, 0.1800, 70000),
        _raw("2002", "Karambit | Doppler (Field-Tested)", KNIFE_DEF, DOPPLER_PAINT, 12, 0.1820, 69000),
        _raw("2003", "Karambit | Doppler (Field-Tested)", KNIFE_DEF, DOPPLER_PAINT, 13, 0.1790, 71500),
        _raw("2004", "Karambit | Doppler (Field-Tested)", KNIFE_DEF, DOPPLER_PAINT, 14, 0.1810, 70500),
        _raw("2005", "Karambit | Doppler (Field-Tested)", KNIFE_DEF, DOPPLER_PAINT, 15, 0.1830, 68500),
    ]
    return rows
