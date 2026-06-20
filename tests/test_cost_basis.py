from cs2_arb.csfloat_client import CSFloatClient


class FakeClient(CSFloatClient):
    """Override _get to return canned /me and /me/trades payloads (no network)."""

    def __init__(self, me_id, trades):
        super().__init__(api_key="x", min_interval=0.0)
        self._me_id = me_id
        self._trades = trades

    def _get(self, path, params):
        if path == "/me":
            return {"user": {"steam_id": self._me_id}}
        if path == "/me/trades":
            return {"trades": self._trades, "count": len(self._trades)}
        raise AssertionError(path)


def _trade(buyer, name, price):
    return {"buyer_id": buyer, "contract": {"price": price,
            "item": {"market_hash_name": name}}}


def test_cost_basis_keeps_only_my_purchases():
    c = FakeClient("ME", [
        _trade("ME", "AK-47 | Bloodsport (Field-Tested)", 14401),
        _trade("ME", "AWP | Chrome Cannon (Minimal Wear)", 3870),
        _trade("SOMEONE_ELSE", "Karambit | Doppler", 70000),  # a sale -> ignored
    ])
    cb = c.cost_basis_by_name()
    assert cb == {
        "AK-47 | Bloodsport (Field-Tested)": 14401,
        "AWP | Chrome Cannon (Minimal Wear)": 3870,
    }


def test_most_recent_duplicate_wins():
    c = FakeClient("ME", [
        _trade("ME", "AK-47 | Bloodsport (Field-Tested)", 12000),
        _trade("ME", "AK-47 | Bloodsport (Field-Tested)", 14401),  # later -> wins
    ])
    assert c.cost_basis_by_name()["AK-47 | Bloodsport (Field-Tested)"] == 14401
