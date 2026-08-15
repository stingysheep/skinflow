from skinflow_api.infrastructure.platforms.youpin.browser import extract_dom_prices


def test_extract_dom_prices_reads_visible_yuan_values_in_order() -> None:
    assert extract_dom_prices([
        "卖家 A ¥1.12",
        "¥1.13 · 极速发货",
        "¥1.16",
    ]) == [112, 113, 116]


def test_extract_dom_prices_ignores_rows_without_currency() -> None:
    assert extract_dom_prices(["数量 10", "参考价格 --", "已售 3"]) == []
