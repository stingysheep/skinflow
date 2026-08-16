from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SteamListingStatus:
    listing_id: str
    status: str
    sold_at: int | None = None
    buyer_pays: int | None = None
    seller_proceeds: int | None = None
    external_ref: str | None = None


class SteamListingStatusPort(Protocol):
    def statuses(self, listing_ids: tuple[str, ...]) -> dict[str, SteamListingStatus]: ...


class ListingReconciliationStore(Protocol):
    def list_reconciliation_items(self) -> list[dict]: ...
    def mark_checked(self, item_id: str, checked_at: int, error: str | None = None) -> None: ...
    def mark_sold(
        self, item_id: str, sale_fill_id: str, sold_at: int, receive_total: int
    ) -> None: ...
    def mark_cancelled(self, item_id: str, checked_at: int) -> None: ...
    def mark_active(
        self, item_id: str, checked_at: int, steam_listing_id: str | None = None
    ) -> None: ...


class ExternalSaleLedger(Protocol):
    def record_external_sale(self, **kwargs) -> dict: ...


class ListingReconciliationService:
    _MISSING_UNCERTAIN_GRACE_MS = 30_000

    def __init__(
        self,
        store: ListingReconciliationStore,
        status_port: SteamListingStatusPort,
        ledger: ExternalSaleLedger,
    ) -> None:
        self._store = store
        self._status_port = status_port
        self._ledger = ledger

    def reconcile(self) -> dict:
        items = self._store.list_reconciliation_items()
        listing_ids = tuple(
            dict.fromkeys(
                str(identifier)
                for item in items
                if item.get("status")
                in {"submitting", "active", "pending_confirmation", "pending_reconciliation"}
                for identifier in (item.get("steam_listing_id"), item.get("assetid"))
                if identifier
            )
        )
        if not listing_ids:
            return {"checked": 0, "sold": 0, "cancelled": 0, "errors": 0}
        try:
            statuses = self._status_port.statuses(listing_ids)
        except Exception as error:
            now = int(time.time() * 1000)
            for item in items:
                if item.get("steam_listing_id") or item.get("assetid"):
                    self._store.mark_checked(item["id"], now, type(error).__name__)
            return {"checked": 0, "sold": 0, "cancelled": 0, "errors": len(listing_ids)}

        summary = {"checked": 0, "sold": 0, "cancelled": 0, "errors": 0}
        for item in items:
            tracking_id = str(item.get("steam_listing_id") or item.get("assetid") or "")
            listing_status = statuses.get(str(item.get("steam_listing_id") or ""))
            asset_status = statuses.get(str(item.get("assetid") or ""))
            listing_is_synthetic_missing = (
                listing_status is not None
                and (listing_status.external_ref or "").startswith("steam:market-missing:")
            )
            status = (
                asset_status
                if listing_is_synthetic_missing and asset_status is not None
                else listing_status or asset_status
            )
            if not tracking_id or status is None:
                continue
            now = int(time.time() * 1000)
            summary["checked"] += 1
            if status.status == "sold":
                sold_at = status.sold_at or now
                receive_total = status.seller_proceeds
                if receive_total is None:
                    receive_total = self._derived_proceeds(item)
                if receive_total is None:
                    self._store.mark_checked(item["id"], now, "STEAM_SALE_AMOUNT_MISSING")
                    summary["errors"] += 1
                    continue
                external_ref = status.external_ref or f"steam:listing:{tracking_id}"
                try:
                    fill = self._ledger.record_external_sale(
                        market_hash_name=item["market_hash_name"],
                        quantity=1,
                        receive_total=receive_total,
                        sold_at=sold_at,
                        listing_item_id=item["id"],
                        external_ref=external_ref,
                    )
                    self._store.mark_sold(item["id"], fill["fill_id"], sold_at, receive_total)
                    summary["sold"] += 1
                except Exception as error:
                    self._store.mark_checked(item["id"], now, type(error).__name__)
                    summary["errors"] += 1
            elif status.status == "cancelled":
                missing_uncertain = (
                    (status.external_ref or "").startswith("steam:market-missing:")
                    and item.get("status") == "pending_reconciliation"
                )
                if missing_uncertain:
                    submitted_at = int(
                        item.get("submission_started_at") or item.get("request_created_at") or 0
                    )
                    if submitted_at and now - submitted_at < self._MISSING_UNCERTAIN_GRACE_MS:
                        self._store.mark_checked(item["id"], now)
                        continue
                if (
                    (status.external_ref or "").startswith("steam:market-missing:")
                    and item.get("status") == "pending_confirmation"
                ):
                    # Steam's market pages do not expose mobile confirmations. Absence is
                    # not proof of cancellation, so retain the explicit submit response.
                    self._store.mark_checked(item["id"], now)
                    continue
                self._store.mark_cancelled(item["id"], now)
                summary["cancelled"] += 1
            elif status.status == "active":
                self._store.mark_active(item["id"], now, status.listing_id)
            else:
                self._store.mark_checked(item["id"], now)
        return summary

    @staticmethod
    def _derived_proceeds(item: dict) -> int | None:
        value = item.get("seller_proceeds")
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return None
        return amount if amount >= 0 else None
