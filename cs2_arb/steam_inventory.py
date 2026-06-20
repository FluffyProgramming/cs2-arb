"""Auto-discover holdings from a public Steam inventory.

Steam gives you WHAT you own (market_hash_name, stickers, inspect link) but NOT
the float. We resolve float per item via the CSFloat inspect API, then you layer
on the only two facts no API knows: cost basis and reserve.

Flow:
    raw = fetch_inventory(steam_id64)
    items = parse_inventory(raw)                 # name + inspect link, no float
    enrich_floats(items, InspectClient(...))     # adds float/paint indices
    -> merge with your cost_basis/reserve overrides to build Holding objects
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

# count is capped at 2000/request by Steam; a User-Agent is required (else 400).
STEAM_INVENTORY_URL = "https://steamcommunity.com/inventory/{sid}/730/2?l=english&count=2000"
_UA = "Mozilla/5.0 (cs2-arb-agent)"


@dataclass
class InventoryItem:
    asset_id: str
    market_hash_name: str
    inspect_link: Optional[str]
    def_index: Optional[int] = None
    paint_index: Optional[int] = None
    paint_seed: Optional[int] = None
    float_value: Optional[float] = None


def _resolve_inspect_link(template: str, asset_id: str, steam_id64: str) -> str:
    return (
        template.replace("%assetid%", asset_id)
        .replace("%owner_steamid%", steam_id64)
    )


def parse_inventory(raw: dict, steam_id64: str) -> list[InventoryItem]:
    """Join the `assets` and `descriptions` arrays into flat InventoryItems.

    Pure function (no network) so it's unit-testable on a fixture.
    """
    descriptions = {
        (d["classid"], d.get("instanceid", "0")): d
        for d in raw.get("descriptions", [])
    }
    items: list[InventoryItem] = []
    for asset in raw.get("assets", []):
        key = (asset["classid"], asset.get("instanceid", "0"))
        desc = descriptions.get(key)
        if not desc:
            continue
        inspect = None
        for action in desc.get("actions", []) or []:
            if "inspect" in action.get("name", "").lower() or "%assetid%" in action.get("link", ""):
                inspect = _resolve_inspect_link(action["link"], asset["assetid"], steam_id64)
                break
        # Keep weapons/knives (they have an inspect action) even when a trade
        # hold has temporarily flipped marketable=0; drop cases/coins/medals.
        if inspect is None:
            continue
        items.append(
            InventoryItem(
                asset_id=asset["assetid"],
                market_hash_name=desc.get("market_hash_name", ""),
                inspect_link=inspect,
            )
        )
    return items


def fetch_inventory(steam_id64: str, timeout: int = 30) -> dict:
    """Fetch a public CS2 inventory. Raises on private/empty inventories."""
    url = STEAM_INVENTORY_URL.format(sid=steam_id64)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if not data or not data.get("assets"):
        raise RuntimeError("inventory empty or private — make it public to use auto-discovery")
    return data


class InspectClient:
    """Resolves float/paint data from a CS2 inspect link via the CSFloat inspect API."""

    def __init__(self, base: str = "https://api.csgofloat.com", min_interval: float = 2.0):
        self.base = base.rstrip("/")
        self.min_interval = min_interval
        self._last = 0.0

    def lookup(self, inspect_link: str, timeout: int = 30) -> dict:
        elapsed = time.time() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        url = f"{self.base}/?url={urllib.parse.quote(inspect_link, safe='')}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        self._last = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())


def enrich_floats(items: list[InventoryItem], client: InspectClient) -> None:
    """Populate float/paint fields in-place. Skips items without an inspect link."""
    for it in items:
        if not it.inspect_link:
            continue
        data = client.lookup(it.inspect_link)
        info = data.get("iteminfo", data)  # csgofloat wraps in "iteminfo"
        it.float_value = info.get("floatvalue")
        it.def_index = info.get("defindex")
        it.paint_index = info.get("paintindex")
        it.paint_seed = info.get("paintseed")
