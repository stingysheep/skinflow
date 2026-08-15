from __future__ import annotations

from datetime import UTC, datetime

from skinflow_api.application.listing.reconciliation import SteamListingStatus
from skinflow_api.application.scan.upstream_errors import UpstreamUnavailable
from skinflow_api.infrastructure.http.client import HttpClient

from .session import InMemorySteamSession

MY_LISTINGS_URL = "https://steamcommunity.com/market/mylistings"
MY_HISTORY_URL = "https://steamcommunity.com/market/myhistory"


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
            active = self._client.request_json(
                f"{MY_LISTINGS_URL}?start=0&count=100&l=schinese&currency=23",
                headers=headers,
            )
            history = self._client.request_json(
                f"{MY_HISTORY_URL}?start=0&count=100&l=schinese&currency=23",
                headers=headers,
            )
        except UpstreamUnavailable as error:
            if error.status_code in {401, 403}:
                self._session.mark_expired()
                raise PermissionError("Steam session expired") from error
            raise
        result: dict[str, SteamListingStatus] = {}
        wanted = set(listing_ids)
        for row in _rows(active, "listings"):
            listing_id = _listing_id(row)
            if listing_id in wanted:
                result[listing_id] = _parse_row(listing_id, row, "active")
        for row in _rows(history, "events"):
            listing_id = _listing_id(row)
            if listing_id not in wanted or listing_id in result:
                continue
            status = "sold" if _is_sold(row) else "cancelled"
            result[listing_id] = _parse_row(listing_id, row, status)
        return result


def _rows(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key) or payload.get("results") or []
    return [row for row in rows if isinstance(row, dict)]


def _listing_id(row: dict) -> str:
    for key in ("listingid", "listing_id", "assetid"):
        value = row.get(key)
        if value:
            return str(value)
    return ""


def _is_sold(row: dict) -> bool:
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("event_type", "type", "description", "status")
    )
    return any(token in text for token in ("sold", "sale", "购买", "售出"))


def _parse_row(listing_id: str, row: dict, status: str) -> SteamListingStatus:
    sold_at = _timestamp(row.get("time") or row.get("timestamp") or row.get("date"))
    seller_proceeds = _money(row.get("received") or row.get("seller_proceeds") or row.get("amount"))
    buyer_pays = _money(row.get("price") or row.get("buyer_pays"))
    return SteamListingStatus(
        listing_id=listing_id,
        status=status,
        sold_at=sold_at,
        buyer_pays=buyer_pays,
        seller_proceeds=seller_proceeds,
        external_ref=f"steam:listing:{listing_id}",
    )


def _money(value: object) -> int | None:
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return None


def _timestamp(value: object) -> int | None:
    if isinstance(value, int | float):
        return int(value * 1000 if value < 10_000_000_000 else value)
    if isinstance(value, str):
        try:
            return int(
                datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000
            )
        except ValueError:
            return None
    return None
