from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from urllib.parse import urlencode

from skinflow_api.application.inventory.errors import (
    InventoryRateLimited,
    InventoryUnavailable,
    SteamSessionExpired,
)
from skinflow_api.application.inventory.models import InventoryAsset
from skinflow_api.application.scan.upstream_errors import RateLimited, UpstreamUnavailable
from skinflow_api.infrastructure.http.client import HttpClient

from .session import InMemorySteamSession

COMMUNITY_URL = "https://steamcommunity.com"
IMAGE_URL = "https://community.cloudflare.steamstatic.com/economy/image/"
CONTEXT_IDS = ("2", "16")
MAX_PAGES_PER_CONTEXT = 20
RETRY_DELAYS_SECONDS = (2.0, 4.0, 8.0)


def parse_inventory_page(data: dict, contextid: str) -> tuple[InventoryAsset, ...]:
    descriptions = {
        (str(row.get("classid", "")), str(row.get("instanceid", "0"))): row
        for row in data.get("descriptions", [])
        if isinstance(row, dict)
    }
    assets: list[InventoryAsset] = []
    for row in data.get("assets", []):
        if not isinstance(row, dict):
            continue
        classid = str(row.get("classid", ""))
        instanceid = str(row.get("instanceid", "0"))
        description = descriptions.get((classid, instanceid))
        if description is None:
            continue
        name = str(description.get("market_hash_name") or "")
        assetid = str(row.get("assetid") or "")
        if not name or not assetid:
            continue
        owner_lines = description.get("owner_descriptions") or []
        hold_text = (
            " ".join(
                str(line.get("value") or "").strip()
                for line in owner_lines
                if isinstance(line, dict) and str(line.get("value") or "").strip()
            )
            or None
        )
        wear_text = _wear_text(description)
        icon_path = str(description.get("icon_url") or "")
        assets.append(
            InventoryAsset(
                platform="steam",
                appid=730,
                contextid=contextid,
                assetid=assetid,
                market_hash_name=name,
                display_name=str(description.get("name") or name),
                image_url=f"{IMAGE_URL}{icon_path}" if icon_path else "",
                classid=classid,
                instanceid=instanceid,
                marketable=bool(description.get("marketable")),
                tradable=bool(description.get("tradable")),
                hold_text=hold_text,
                wear_text=wear_text,
            )
        )
    return tuple(assets)


def _wear_text(description: dict) -> str | None:
    for tag in description.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        category = str(tag.get("category") or tag.get("internal_name") or "").lower()
        if category in {"exterior", "wearcategory", "磨损度"}:
            value = str(tag.get("localized_tag_name") or tag.get("tag_name") or "").strip()
            if value:
                return value
    for line in description.get("descriptions") or []:
        if not isinstance(line, dict):
            continue
        value = re.sub(r"<[^>]+>", " ", str(line.get("value") or ""))
        match = re.search(r"(?:Float Value|浮动值)\s*:\s*([0-9.]+)", value, re.I)
        if match:
            return f"Float {match.group(1)}"
    return None


class SteamInventoryAdapter:
    def __init__(
        self,
        session: InMemorySteamSession,
        client: HttpClient | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._session = session
        self._client = client or HttpClient()
        self._sleep = sleep

    def fetch_inventory(self) -> tuple[InventoryAsset, ...]:
        credentials = self._session.credentials()
        assets: list[InventoryAsset] = []
        for contextid in CONTEXT_IDS:
            assets.extend(
                self._fetch_context(credentials.steamid64, credentials.cookie_header, contextid)
            )
        return tuple(assets)

    def _fetch_context(
        self, steamid64: str, cookie: str, contextid: str
    ) -> Iterable[InventoryAsset]:
        seen: set[str] = set()
        start_assetid: str | None = None
        items: list[InventoryAsset] = []
        for _ in range(MAX_PAGES_PER_CONTEXT):
            query = {"l": "schinese", "count": "500"}
            if start_assetid:
                query["start_assetid"] = start_assetid
            url = f"{COMMUNITY_URL}/inventory/{steamid64}/730/{contextid}?{urlencode(query)}"
            data = self._request_page(url, steamid64, cookie)
            if not data.get("success"):
                raise InventoryUnavailable("Steam 库存返回了无效响应，请稍后重试")
            page = [
                item for item in parse_inventory_page(data, contextid) if item.assetid not in seen
            ]
            items.extend(page)
            seen.update(item.assetid for item in page)
            next_assetid = data.get("last_assetid")
            if not data.get("more_items") or not next_assetid:
                break
            start_assetid = str(next_assetid)
        return items

    def _request_page(self, url: str, steamid64: str, cookie: str) -> dict:
        last_rate_limit: RateLimited | None = None
        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            try:
                return self._client.request_json(
                    url,
                    headers={
                        "Cookie": cookie,
                        "Referer": f"{COMMUNITY_URL}/profiles/{steamid64}/inventory/",
                    },
                )
            except RateLimited as error:
                last_rate_limit = error
                if attempt == len(RETRY_DELAYS_SECONDS):
                    break
                delay = error.retry_after_seconds or RETRY_DELAYS_SECONDS[attempt]
                self._sleep(min(float(delay), RETRY_DELAYS_SECONDS[-1]))
            except UpstreamUnavailable as error:
                if error.status_code in {401, 403}:
                    self._session.mark_expired()
                    raise SteamSessionExpired("Steam 会话已过期，请重新登录") from error
                raise InventoryUnavailable("Steam 库存服务暂时不可用，请稍后重试") from error
        raise InventoryRateLimited(
            last_rate_limit.retry_after_seconds if last_rate_limit else None
        ) from last_rate_limit
