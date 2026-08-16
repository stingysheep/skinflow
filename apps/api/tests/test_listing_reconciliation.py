from skinflow_api.application.listing.reconciliation import (
    ListingReconciliationService,
    SteamListingStatus,
)


class Store:
    def __init__(self):
        self.items = [{
            "id": "item-1",
            "status": "active",
            "steam_listing_id": "listing-1",
            "market_hash_name": "AK-47 | Slate",
            "seller_proceeds": 123,
        }]
        self.sold = []

    def list_reconciliation_items(self):
        return self.items

    def mark_checked(self, item_id, checked_at, error=None):
        self.items[0]["last_checked_at"] = checked_at
        self.items[0]["reconcile_error"] = error

    def mark_sold(self, item_id, sale_fill_id, sold_at, receive_total):
        self.sold.append((item_id, sale_fill_id, sold_at, receive_total))

    def mark_cancelled(self, item_id, checked_at):
        self.items[0]["status"] = "cancelled"

    def mark_active(self, item_id, checked_at):
        self.items[0]["status"] = "active"


class StatusPort:
    def statuses(self, listing_ids):
        return {
            listing_ids[0]: SteamListingStatus(
                listing_ids[0], "sold", sold_at=1000, seller_proceeds=123
            )
        }


class Ledger:
    def __init__(self):
        self.calls = []

    def record_external_sale(self, **kwargs):
        self.calls.append(kwargs)
        return {"fill_id": "fill-1"}


def test_reconciliation_records_sold_once_and_marks_item():
    store = Store()
    ledger = Ledger()
    summary = ListingReconciliationService(store, StatusPort(), ledger).reconcile()

    assert summary == {"checked": 1, "sold": 1, "cancelled": 0, "errors": 0}
    assert len(ledger.calls) == 1
    assert store.sold == [("item-1", "fill-1", 1000, 123)]


def test_reconciliation_uses_assetid_when_listing_id_is_missing():
    store = Store()
    store.items[0].pop("steam_listing_id")
    store.items[0]["assetid"] = "asset-1"
    ledger = Ledger()
    summary = ListingReconciliationService(store, StatusPort(), ledger).reconcile()

    assert summary["sold"] == 1
    assert ledger.calls[0]["external_ref"] == "steam:listing:asset-1"


def test_reconciliation_syncs_cancelled_assetid_status():
    store = Store()
    store.items[0].pop("steam_listing_id")
    store.items[0]["assetid"] = "asset-1"

    class CancelledStatusPort:
        def statuses(self, listing_ids):
            return {listing_ids[0]: SteamListingStatus(listing_ids[0], "cancelled")}

    summary = ListingReconciliationService(store, CancelledStatusPort(), Ledger()).reconcile()

    assert summary == {"checked": 1, "sold": 0, "cancelled": 1, "errors": 0}
    assert store.items[0]["status"] == "cancelled"


def test_reconciliation_includes_pending_confirmation_items():
    store = Store()
    store.items[0]["status"] = "pending_confirmation"

    class ActiveStatusPort:
        def statuses(self, listing_ids):
            return {listing_ids[0]: SteamListingStatus(listing_ids[0], "active")}

    summary = ListingReconciliationService(store, ActiveStatusPort(), Ledger()).reconcile()

    assert summary["checked"] == 1
    assert store.items[0]["status"] == "active"


def test_reconciliation_promotes_pending_transport_to_active():
    store = Store()
    store.items[0]["status"] = "pending_reconciliation"

    class ActiveStatusPort:
        def statuses(self, listing_ids):
            return {listing_ids[0]: SteamListingStatus(listing_ids[0], "active")}

    summary = ListingReconciliationService(store, ActiveStatusPort(), Ledger()).reconcile()

    assert summary["checked"] == 1
    assert store.items[0]["status"] == "active"
