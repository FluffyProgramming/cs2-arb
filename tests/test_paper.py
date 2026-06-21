from cs2_arb.paper import PaperBook, PaperConfig, HOLD_SECONDS

CFG = PaperConfig(bankroll_cents=100_000, sell_fee=0.02)


def buy(book, id, buy, fair, now=1000.0):
    return book.record_buy(id=id, label=f"item{id}", market_hash_name=f"item{id}",
                           rarity=6, float_value=0.2, def_index=7, paint_index=1,
                           category=1, buy_cents=buy, fair_cents=fair, now=now)


def test_buy_deducts_cash_and_locks_capital():
    b = PaperBook(CFG)
    assert buy(b, "1", 20000, 24000) is True
    assert b.cash_cents == 80000
    assert len(b.open_positions()) == 1


def test_cannot_overspend_bankroll():
    b = PaperBook(CFG)
    assert buy(b, "1", 90000, 100000) is True
    assert buy(b, "2", 20000, 30000) is False     # only $100 cash left
    assert b.cash_cents == 10000


def test_dedupe_same_listing():
    b = PaperBook(CFG)
    assert buy(b, "1", 20000, 24000) is True
    assert buy(b, "1", 20000, 24000) is False     # same id not re-bought


def test_no_sell_before_7_day_hold():
    b = PaperBook(CFG)
    buy(b, "1", 20000, 24000, now=1000.0)
    sold = b.settle_due(lambda p: 30000, now=1000.0 + HOLD_SECONDS - 10)
    assert sold == [] and len(b.open_positions()) == 1


def test_sell_after_hold_realizes_pl():
    b = PaperBook(CFG)
    buy(b, "1", 20000, 24000, now=1000.0)
    sold = b.settle_due(lambda p: 25000, now=1000.0 + HOLD_SECONDS + 1)
    assert len(sold) == 1
    # proceeds = 25000*0.98 = 24500 ; net = 24500 - 20000 = 4500
    assert sold[0].net_cents == 4500
    assert b.cash_cents == 100000 - 20000 + 24500


def test_metrics_win_rate_and_return():
    b = PaperBook(CFG)
    buy(b, "1", 20000, 24000, now=0.0)
    buy(b, "2", 10000, 11000, now=0.0)
    # item1 sells up, item2 sells down
    prices = {"1": 25000, "2": 9000}
    b.settle_due(lambda p: prices[p.id], now=HOLD_SECONDS + 1)
    m = b.metrics(lambda p: 0)
    assert m["closed_count"] == 2
    assert m["win_rate"] == 0.5          # one win, one loss
    assert m["open_count"] == 0


def test_persistence_roundtrip(tmp_path):
    p = str(tmp_path / "book.json")
    b = PaperBook(CFG, path=p)
    buy(b, "1", 20000, 24000)
    b.save()
    b2 = PaperBook.load(p, CFG)
    assert b2.cash_cents == 80000
    assert len(b2.open_positions()) == 1
    assert b2.open_positions()[0].def_index == 7
