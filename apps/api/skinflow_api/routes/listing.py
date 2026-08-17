from fastapi import APIRouter
from pydantic import BaseModel, Field

from skinflow_api.application.listing import ListingService
from skinflow_api.application.listing.models import (
    MAX_LISTING_PREVIEW_ASSETS,
    ListingGroupSelection,
    ListingSelection,
)


class AssetSelection(BaseModel):
    platform: str = "steam"
    appid: int = 730
    contextid: str = Field(min_length=1, max_length=20)
    assetid: str = Field(min_length=1, max_length=40)
    buyer_pays: int | None = Field(default=None, ge=1)


class GroupSelection(BaseModel):
    market_hash_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=MAX_LISTING_PREVIEW_ASSETS)
    buyer_pays: int | None = Field(default=None, ge=1)


class PreviewRequest(BaseModel):
    items: list[AssetSelection] = Field(
        default_factory=list, max_length=MAX_LISTING_PREVIEW_ASSETS
    )
    groups: list[GroupSelection] = Field(
        default_factory=list, max_length=MAX_LISTING_PREVIEW_ASSETS
    )


class SubmitRequest(BaseModel):
    preview_id: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=100)
    confirmed: bool
    prices: dict[str, int] = Field(default_factory=dict)


class CancelRequest(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=100)


def create_listing_router(service: ListingService, reconciler=None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["listings"])

    @router.post("/listing-previews", status_code=201)
    def preview(request: PreviewRequest) -> dict:
        if bool(request.items) == bool(request.groups):
            raise ValueError("provide exactly one of items or groups")
        if request.groups:
            return service.create_grouped_preview(
                tuple(
                    ListingGroupSelection(item.market_hash_name, item.quantity, item.buyer_pays)
                    for item in request.groups
                )
            )
        selections = tuple(
            ListingSelection(
                item.platform, item.appid, item.contextid, item.assetid, item.buyer_pays
            )
            for item in request.items
        )
        return service.create_preview(selections)

    @router.post("/listing-requests", status_code=201)
    def submit(request: SubmitRequest) -> dict:
        if not request.confirmed:
            raise ValueError("explicit listing confirmation is required")
        submit_background = getattr(service, "submit_background", None)
        if submit_background is not None:
            return submit_background(request.preview_id, request.idempotency_key, request.prices)
        return service.submit(request.preview_id, request.idempotency_key, request.prices)

    @router.patch("/listing-previews/{preview_id}")
    def update_preview(preview_id: str, prices: dict[str, int]) -> dict:
        return service.update_preview_prices(preview_id, prices)

    @router.get("/listing-requests")
    def requests() -> dict:
        return {"items": service.list_requests()}

    @router.post("/listing-requests/cancel")
    async def cancel(request: CancelRequest) -> dict:
        result = service.cancel_items(tuple(request.item_ids))
        missing = tuple(
            item["id"]
            for item in result["items"]
            if item.get("message") == "STEAM_LISTING_ID_MISSING"
        )
        if not missing or reconciler is None:
            return result
        # Reconcile only mobile-confirmed items whose real Steam id is still missing.
        await reconciler.reconcile_now()
        retried = {item["id"]: item for item in service.cancel_items(missing)["items"]}
        return {"items": [retried.get(item["id"], item) for item in result["items"]]}

    @router.post("/listing-requests/reconcile")
    async def reconcile() -> dict:
        if reconciler is None:
            return {"checked": 0, "sold": 0, "cancelled": 0, "errors": 0}
        return await reconciler.reconcile_now()

    @router.get("/listing-requests/{request_id}")
    def request_status(request_id: str) -> dict:
        return service.get_request(request_id)

    return router
