"""Wear-tier logic and float ranking.

CS2 exterior is derived from the float value. Lower float is generally rarer
and more valuable within a tier, which is why a float-aware comparable beats a
flat market price.
"""

from __future__ import annotations

from typing import Sequence

# (name, lower_inclusive, upper_exclusive). BS upper is inclusive of 1.0.
WEAR_TIERS: tuple[tuple[str, float, float], ...] = (
    ("Factory New", 0.00, 0.07),
    ("Minimal Wear", 0.07, 0.15),
    ("Field-Tested", 0.15, 0.38),
    ("Well-Worn", 0.38, 0.45),
    ("Battle-Scarred", 0.45, 1.0001),
)


def wear_tier(float_value: float) -> str:
    """Return the exterior name for a float value."""
    if float_value < 0 or float_value > 1:
        raise ValueError(f"float out of range: {float_value}")
    for name, lo, hi in WEAR_TIERS:
        if lo <= float_value < hi:
            return name
    return "Battle-Scarred"  # exactly 1.0


def float_rank_pct(target_float: float, comp_floats: Sequence[float]) -> float:
    """Fraction of comparable floats strictly lower than the target.

    0.0  -> target holds the lowest float in the comp set (rarest / best).
    1.0  -> target holds the highest float (worst).
    Returns 0.0 when there are no comps.
    """
    if not comp_floats:
        return 0.0
    lower = sum(1 for f in comp_floats if f < target_float)
    return lower / len(comp_floats)
