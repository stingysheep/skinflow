from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from skinflow_api.application.listing.reconciliation import SteamListingStatus
from skinflow_api.application.scan.upstream_errors import UpstreamUnavailable
from skinflow_api.infrastructure.http.client import HttpClient

from .session import InMemorySteamSession

MY_LISTINGS_URL = "https://steamcommunity.com/market/mylistings"
MY_HISTORY_URL = "https://steamcommunity.com/market/myhistory"
HOVER_PATTERN = re.compile(
    r"CreateItemHoverFromContainer\(\s*g_rgAssets,\s*'(?P<element>[^']+)',"
    r"\s*\d+,\s*'[^']+',\s*'(?P<assetid>[^']+)'"
)
LISTING_ROW_PATTERN = re.compile(r"^mylisting_(?P<listing_id>\d+)$")
AWAITING_CONFIRMATION_PATTERN = re.compile(
    r"(?:CancelMarketListingConfirmation\s*\(|"
    r"RemoveListingDialog\.Show\([^;]*,\s*(?:true|1)\s*\))",
    re.IGNORECASE,
)
MARKET_DATE_PATTERN = re.compile(
    r"(?:(?P<year>\d{4})\s*年\s*)?"
    r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
)
MONEY_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


class SteamListingStatusAdapter:
    def __init__(self, session: InMemorySteamSession, client: HttpClient | None = None) -> None:
        self._session = session
        self._client = client or HttpClient()

    def statuses(self, listing_ids: tuple[str, ...]) -> dict[str, SteamListingStatus]:
        credentials = self._session.credentials()
        headers = {
            "Cookie": credentials.cookie_header,
            "Referer": "https://steamcommunity.com/market/",
        }
        try:
            result: dict[str, SteamListingStatus] = {}
            wanted = set(listing_ids)
            _, active_observed = self._fetch_pages(
                MY_LISTINGS_URL, headers, wanted, result, "active"
            )
            remaining = wanted.difference(result)
            history_complete, history_observed = self._fetch_pages(
                MY_HISTORY_URL, headers, remaining, result, "history"
            )
        except UpstreamUnavailable as error:
            if error.status_code in {401, 403}:
                self._session.mark_expired()
                raise PermissionError("Steam session expired") from error
            raise
        observed = active_observed | history_observed
        for missing in wanted.difference(result).difference(observed) if history_complete else ():
            result[missing] = SteamListingStatus(
                listing_id=missing,
                status="cancelled",
                external_ref=f"steam:market-missing:{missing}",
            )
        return result

    def _fetch_pages(
        self,
        endpoint: str,
        headers: dict[str, str],
        wanted: set[str],
        result: dict[str, SteamListingStatus],
        source: str,
    ) -> tuple[bool, set[str]]:
        if not wanted:
            return True, set()
        observed: set[str] = set()
        start = 0
        while True:
            payload = self._client.request_json(
                f"{endpoint}?start={start}&count=100&l=schinese&currency=23",
                headers=headers,
            )
            if not payload.get("success", True):
                raise UpstreamUnavailable("Steam market response rejected")
            observed.update(_collect_statuses(result, wanted, payload, source))
            if wanted.issubset(result):
                return True, observed
            total_count = int(payload.get("total_count") or 0)
            if total_count <= start + 100:
                return True, observed
            start += 100


@dataclass(slots=True)
class _MarketRow:
    row_id: str
    text: list[str] = field(default_factory=list)
    price_text: list[str] = field(default_factory=list)
    awaiting_confirmation: bool = False


class _MarketRowsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[_MarketRow] = []
        self._current: _MarketRow | None = None
        self._row_div_depth = 0
        self._class_stack: list[set[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        self._class_stack.append(classes)
        if self._current is None:
            if tag == "div" and "market_listing_row" in classes:
                self._current = _MarketRow(str(attributes.get("id") or ""))
                self._row_div_depth = 1
            return
        if any(
            AWAITING_CONFIRMATION_PATTERN.search(str(value or ""))
            for value in attributes.values()
        ):
            self._current.awaiting_confirmation = True
        if tag == "div":
            self._row_div_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._current is not None and tag == "div":
            self._row_div_depth -= 1
            if self._row_div_depth == 0:
                self.rows.append(self._current)
                self._current = None
        if self._class_stack:
            self._class_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        text = " ".join(data.split())
        if not text:
            return
        self._current.text.append(text)
        if any("market_listing_price" in classes for classes in self._class_stack):
            self._current.price_text.append(text)


def _collect_statuses(
    result: dict[str, SteamListingStatus],
    wanted: set[str],
    payload: dict,
    source: str,
) -> set[str]:
    parser = _MarketRowsParser()
    parser.feed(str(payload.get("results_html") or ""))
    assets = _hover_assets(str(payload.get("hovers") or ""))
    observed: set[str] = set()
    for row in parser.rows:
        assetid = assets.get(row.row_id, "")
        listing_match = LISTING_ROW_PATTERN.fullmatch(row.row_id)
        listing_id = listing_match.group("listing_id") if listing_match else ""
        keys = tuple(key for key in (listing_id, assetid) if key in wanted)
        if not keys:
            continue
        observed.update(keys)
        status = (
            "pending_confirmation" if row.awaiting_confirmation else "active"
        ) if source == "active" else _history_status(row)
        if status is None:
            continue
        identity = listing_id or assetid
        parsed = SteamListingStatus(
            listing_id=identity,
            status=status,
            sold_at=_market_timestamp(" ".join(row.text)) if status == "sold" else None,
            seller_proceeds=_money(" ".join(row.price_text)) if status == "sold" else None,
            external_ref=(
                f"steam:market-history:{row.row_id}"
                if source == "history"
                else f"steam:listing:{identity}"
            ),
        )
        for key in keys:
            if key not in result:
                result[key] = parsed
    return observed


def _hover_assets(script: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for match in HOVER_PATTERN.finditer(script):
        element = match.group("element")
        if element.endswith(("_name", "_image")):
            output[element.rsplit("_", 1)[0]] = match.group("assetid")
    return output


def _history_status(row: _MarketRow) -> str | None:
    text = " ".join(row.text).lower()
    if any(token in text for token in ("sold", "sale", "已售出", "售出")):
        return "sold"
    if any(token in text for token in ("cancelled", "canceled", "已取消", "取消")):
        return "cancelled"
    return None


def _money(value: object) -> int | None:
    match = MONEY_PATTERN.search(str(value or ""))
    if match is None:
        return None
    try:
        return int((Decimal(match.group().replace(",", "")) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        return None


def _timestamp(value: object) -> int | None:
    if isinstance(value, int | float):
        return int(value * 1000 if value < 10_000_000_000 else value)
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000)
        except ValueError:
            return None
    return None


def _market_timestamp(value: str, now: datetime | None = None) -> int | None:
    parsed = _timestamp(value)
    if parsed is not None:
        return parsed
    match = MARKET_DATE_PATTERN.search(value)
    if match is None:
        return None
    current = now or datetime.now().astimezone()
    year = int(match.group("year") or current.year)
    candidate = datetime(
        year,
        int(match.group("month")),
        int(match.group("day")),
        tzinfo=current.tzinfo,
    )
    if match.group("year") is None and candidate > current + timedelta(days=31):
        candidate = candidate.replace(year=current.year - 1)
    return int(candidate.timestamp() * 1000)
