"""Minimal CSFloat API client (stdlib only).

Real, usable client for https://csfloat.com/api/v1. Handles auth, the documented
listing filters, cursor pagination, and 429/5xx backoff. Used live once you set
CSFLOAT_API_KEY; the demo uses fixtures so no key is needed to see it work.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator, Optional

from .models import Listing, Sticker

BASE_URL = "https://csfloat.com/api/v1"


def parse_listing(raw: dict) -> Listing:
    """Map a raw CSFloat listing dict to our Listing model."""
    item = raw["item"]
    scm = item.get("scm") or {}
    stickers = tuple(
        Sticker(
            name=s.get("name", ""),
            slot=s.get("slot", 0),
            scm_price_cents=(s.get("scm") or {}).get("price", 0),
        )
        for s in item.get("stickers", []) or []
    )
    return Listing(
        id=str(raw["id"]),
        market_hash_name=item["market_hash_name"],
        def_index=item["def_index"],
        paint_index=item["paint_index"],
        paint_seed=item.get("paint_seed", 0),
        float_value=item["float_value"],
        price_cents=raw["price"],
        is_stattrak=item.get("is_stattrak", False),
        is_souvenir=item.get("is_souvenir", False),
        type=raw.get("type", "buy_now"),
        wear_name=item.get("wear_name", ""),
        stickers=stickers,
        url=f"https://csfloat.com/item/{raw['id']}",
        scm_price_cents=scm.get("price", 0) or 0,
        scm_volume=scm.get("volume", 0) or 0,
    )


class CSFloatClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = BASE_URL,
        min_interval: float = 1.0,   # polite floor between requests (seconds)
        max_retries: int = 5,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_request = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _get(self, path: str, params: dict) -> list | dict:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}?{query}" if query else f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = self.api_key

        backoff = 2.0
        for attempt in range(self.max_retries):
            self._throttle()
            req = urllib.request.Request(url, headers=headers)
            try:
                self._last_request = time.time()
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < self.max_retries - 1:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else backoff
                    time.sleep(wait)
                    backoff *= 2
                    continue
                raise
        raise RuntimeError(f"exhausted retries for {url}")

    def get_my_inventory(self) -> list[dict]:
        """Return the authenticated user's CS2 inventory WITH float values.

        Each item includes float_value, def_index, paint_index, paint_seed,
        market_hash_name, is_stattrak/is_souvenir — no inspect links needed.
        Requires a valid API key. This is the fully-automated float source.
        """
        payload = self._get("/me/inventory", {})
        return payload if isinstance(payload, list) else payload.get("data", [])

    def cost_basis_by_name(self) -> dict[str, int]:
        """Map market_hash_name -> price paid (cents) for items you BOUGHT on CSFloat.

        Reads /me/trades and keeps trades where you are the buyer. Matched by name
        because Steam reassigns asset IDs on delivery, so the trade's asset_id no
        longer matches your current inventory. For duplicate skins, the most recent
        purchase wins.
        """
        me = self._get("/me", {})
        my_id = (me.get("user") or {}).get("steam_id")
        trades = self._get("/me/trades", {})
        rows = trades.get("trades", []) if isinstance(trades, dict) else (trades or [])
        out: dict[str, int] = {}
        for t in rows:
            if t.get("buyer_id") != my_id:
                continue
            contract = t.get("contract") or {}
            item = contract.get("item") or {}
            name, price = item.get("market_hash_name"), contract.get("price")
            if name and price is not None:
                out[name] = price
        return out

    def iter_listings(
        self,
        *,
        market_hash_name: Optional[str] = None,
        def_index: Optional[int] = None,
        paint_index: Optional[int] = None,
        paint_seed: Optional[int] = None,
        min_float: Optional[float] = None,
        max_float: Optional[float] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        category: Optional[int] = None,
        sort_by: str = "lowest_price",
        listing_type: Optional[str] = "buy_now",
        max_pages: int = 10,
    ) -> Iterator[Listing]:
        """Yield parsed listings, following cursor pagination (50/page). Prices in cents."""
        cursor = None
        for _ in range(max_pages):
            params = {
                "market_hash_name": market_hash_name,
                "def_index": def_index,
                "paint_index": paint_index,
                "paint_seed": paint_seed,
                "min_float": min_float,
                "max_float": max_float,
                "min_price": min_price,
                "max_price": max_price,
                "category": category,
                "sort_by": sort_by,
                "type": listing_type,
                "limit": 50,
                "cursor": cursor,
            }
            payload = self._get("/listings", params)
            # API returns either a bare list or {"data": [...], "cursor": "..."}
            rows = payload.get("data") if isinstance(payload, dict) else payload
            if not rows:
                break
            for raw in rows:
                yield parse_listing(raw)
            cursor = payload.get("cursor") if isinstance(payload, dict) else None
            if not cursor or len(rows) < 50:
                break
