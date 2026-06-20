from cs2_arb.steam_inventory import InventoryItem, enrich_floats, parse_inventory

RAW = {
    "assets": [
        {"classid": "c1", "instanceid": "i1", "assetid": "A100"},
        {"classid": "c2", "instanceid": "0", "assetid": "A200"},
        {"classid": "c3", "instanceid": "0", "assetid": "A300"},  # no description
    ],
    "descriptions": [
        {
            "classid": "c1", "instanceid": "i1", "marketable": 1,
            "market_hash_name": "AK-47 | Bloodsport (Field-Tested)",
            "actions": [{
                "name": "Inspect in Game...",
                "link": "steam://rungame/730/%owner_steamid%/+csgo_econ_action_preview S%owner_steamid%A%assetid%D123",
            }],
        },
        {
            "classid": "c2", "instanceid": "0", "marketable": 0,  # not marketable -> skip
            "market_hash_name": "Some Case",
        },
    ],
}


def test_parse_joins_assets_and_descriptions():
    items = parse_inventory(RAW, steam_id64="76561190000000000")
    # only the marketable AK with a description survives
    assert len(items) == 1
    it = items[0]
    assert it.asset_id == "A100"
    assert it.market_hash_name == "AK-47 | Bloodsport (Field-Tested)"


def test_inspect_link_placeholders_substituted():
    items = parse_inventory(RAW, steam_id64="76561190000000000")
    link = items[0].inspect_link
    assert "%assetid%" not in link and "%owner_steamid%" not in link
    assert "A100" in link and "76561190000000000" in link


def test_enrich_floats_uses_client(monkeypatch=None):
    items = [InventoryItem(asset_id="A100", market_hash_name="AK", inspect_link="steam://x")]

    class FakeClient:
        def lookup(self, link):
            return {"iteminfo": {"floatvalue": 0.2215, "defindex": 7,
                                 "paintindex": 282, "paintseed": 700}}

    enrich_floats(items, FakeClient())
    assert items[0].float_value == 0.2215
    assert items[0].def_index == 7
    assert items[0].paint_index == 282


def test_enrich_skips_items_without_inspect_link():
    items = [InventoryItem(asset_id="A1", market_hash_name="x", inspect_link=None)]

    class BoomClient:
        def lookup(self, link):
            raise AssertionError("should not be called")

    enrich_floats(items, BoomClient())  # must not raise
    assert items[0].float_value is None
