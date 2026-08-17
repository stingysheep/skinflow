from datetime import datetime, timedelta, timezone

from skinflow_api.infrastructure.platforms.steam.listing_status import (
    SteamListingStatusAdapter,
    _market_timestamp,
)
from skinflow_api.infrastructure.platforms.steam.session import (
    InMemorySteamSession,
    SteamCredentials,
)

ACTIVE_HTML = """
<div class="market_listing_row market_recent_listing_row" id="mylisting_12345">
  <span class="market_listing_price">¥ 17.59</span>
  <span class="market_listing_item_name">格洛克18型</span>
</div>
"""
ACTIVE_HOVERS = """
CreateItemHoverFromContainer(
  g_rgAssets, 'mylisting_12345_name', 730, '2', 'asset-1', 1
);
"""
PENDING_HTML = """
<div class="market_listing_row market_recent_listing_row" id="mylisting_12345">
  <span class="market_listing_price">¥ 17.59</span>
  <span class="market_listing_item_name">格洛克18型</span>
  <a href="javascript:RemoveListingDialog.Show('mylisting', '12345', {}, true)">
    取消
  </a>
</div>
"""
SOLD_HTML = """
<div class="market_listing_row market_recent_listing_row"
     id="history_row_100_101">
  <div class="market_listing_left_cell market_listing_gainorloss">-</div>
  <span class="market_listing_price">¥ 17.59</span>
  <div class="market_listing_right_cell market_listing_listed_date">8 月 16 日</div>
  <div class="market_listing_item_name_block">已售出: 8 月 16 日</div>
</div>
"""
SOLD_HOVERS = """
CreateItemHoverFromContainer(
  g_rgAssets, 'history_row_100_101_name', 730, '2', 'asset-1', 0
);
"""


class Client:
    def __init__(self, *, active: dict, history: dict) -> None:
        self.active = active
        self.history = history

    def request_json(self, url, *, headers=None):
        return self.history if "myhistory" in url else self.active


class PagedHistoryClient(Client):
    def __init__(self) -> None:
        super().__init__(
            active={"success": True, "total_count": 0, "results_html": "", "hovers": ""},
            history={},
        )
        self.calls: list[str] = []

    def request_json(self, url, *, headers=None):
        self.calls.append(url)
        if "mylistings" in url:
            return self.active
        if "start=0" in url:
            return {"success": True, "total_count": 201, "results_html": "", "hovers": ""}
        if "start=100" in url:
            return {
                "success": True,
                "total_count": 201,
                "results_html": SOLD_HTML,
                "hovers": SOLD_HOVERS,
            }
        return {"success": True, "total_count": 201, "results_html": "", "hovers": ""}


def session() -> InMemorySteamSession:
    value = InMemorySteamSession()
    value.set_credentials(SteamCredentials("76561198000000000", "secure", "session"))
    return value


def test_status_adapter_maps_active_listing_to_listing_and_asset_ids() -> None:
    adapter = SteamListingStatusAdapter(
        session(),
        Client(
            active={"success": True, "results_html": ACTIVE_HTML, "hovers": ACTIVE_HOVERS},
            history={"success": True, "results_html": "", "hovers": ""},
        ),
    )

    statuses = adapter.statuses(("12345", "asset-1"))

    assert statuses["12345"].status == "active"
    assert statuses["asset-1"].status == "active"


def test_status_adapter_keeps_awaiting_confirmation_out_of_active_listings() -> None:
    adapter = SteamListingStatusAdapter(
        session(),
        Client(
            active={"success": True, "results_html": PENDING_HTML, "hovers": ACTIVE_HOVERS},
            history={"success": True, "results_html": "", "hovers": ""},
        ),
    )

    statuses = adapter.statuses(("12345", "asset-1"))

    assert statuses["12345"].status == "pending_confirmation"
    assert statuses["asset-1"].status == "pending_confirmation"


def test_status_adapter_reads_sold_asset_and_seller_proceeds_from_history() -> None:
    adapter = SteamListingStatusAdapter(
        session(),
        Client(
            active={"success": True, "results_html": "", "hovers": ""},
            history={"success": True, "results_html": SOLD_HTML, "hovers": SOLD_HOVERS},
        ),
    )

    status = adapter.statuses(("asset-1",))["asset-1"]

    assert status.status == "sold"
    assert status.seller_proceeds == 1759
    assert status.sold_at is not None
    assert status.external_ref == "steam:market-history:history_row_100_101"


def test_status_adapter_ignores_purchase_history_for_pending_listing() -> None:
    purchase_html = SOLD_HTML.replace("已售出", "已购买").replace(
        'market_listing_gainorloss">-', 'market_listing_gainorloss">+'
    )
    adapter = SteamListingStatusAdapter(
        session(),
        Client(
            active={"success": True, "results_html": "", "hovers": ""},
            history={
                "success": True,
                "results_html": purchase_html,
                "hovers": SOLD_HOVERS,
            },
        ),
    )

    assert adapter.statuses(("asset-1",)) == {}


def test_status_adapter_marks_missing_listing_as_cancelled_after_successful_sync() -> None:
    adapter = SteamListingStatusAdapter(
        session(),
        Client(
            active={"success": True, "results_html": "", "hovers": ""},
            history={"success": True, "results_html": "", "hovers": ""},
        ),
    )

    status = adapter.statuses(("asset-1",))["asset-1"]

    assert status.status == "cancelled"


def test_status_adapter_cancels_missing_listing_after_paging_complete_history() -> None:
    adapter = SteamListingStatusAdapter(
        session(),
        Client(
            active={"success": True, "results_html": "", "hovers": ""},
            history={"success": True, "total_count": 101, "results_html": "", "hovers": ""},
        ),
    )

    assert adapter.statuses(("asset-1",))["asset-1"].status == "cancelled"


def test_status_adapter_pages_history_until_sold_listing_is_found() -> None:
    client = PagedHistoryClient()
    adapter = SteamListingStatusAdapter(session(), client)

    status = adapter.statuses(("asset-1",))["asset-1"]

    assert status.status == "sold"
    assert any("start=100" in url and "myhistory" in url for url in client.calls)


def test_market_timestamp_uses_local_year_for_chinese_steam_date() -> None:
    local_tz = timezone(timedelta(hours=8))
    now = datetime(2026, 8, 16, 23, 0, tzinfo=local_tz)

    parsed = _market_timestamp("已售出: 8 月 16 日", now)

    assert parsed == int(datetime(2026, 8, 16, tzinfo=local_tz).timestamp() * 1000)
