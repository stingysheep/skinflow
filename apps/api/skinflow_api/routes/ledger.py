import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from skinflow_api.application.inventory import InventoryService
from skinflow_api.application.ledger import LedgerService


class PurchaseRequest(BaseModel):
    market_hash_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=10000)
    cost_each: int = Field(ge=1)
    purchased_at: int | None = Field(default=None, ge=1)
    venue: str | None = Field(default=None, max_length=40)
    pending_delivery: bool = False


class ReceiveRequest(BaseModel):
    quantity: int = Field(ge=1, le=10000)
    received_at: int | None = Field(default=None, ge=1)


class SaleRequest(BaseModel):
    market_hash_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=10000)
    receive_total: int = Field(ge=0)
    sold_at: int | None = Field(default=None, ge=1)


class HoldingUpdateRequest(BaseModel):
    cost_each: int = Field(ge=1)


def create_ledger_router(
    repository: LedgerService, inventory_service: InventoryService
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["ledger"])

    @router.get("/holdings")
    def holdings() -> dict:
        items = repository.holdings()
        open_quantity = sum(item["open_quantity"] for item in items)
        return {
            "items": items,
            "summary": {"items": len(items), "open_quantity": open_quantity},
        }

    @router.put("/holdings/{market_hash_name}")
    def update_holding(market_hash_name: str, request: HoldingUpdateRequest) -> dict:
        return repository.update_holding_average_cost(market_hash_name, request.cost_each)

    @router.delete("/holdings/{market_hash_name}")
    def delete_holding(market_hash_name: str) -> dict:
        return repository.delete_holding(market_hash_name)

    @router.get("/history")
    def history() -> dict:
        items = repository.history()
        received = sum(item["receive_total"] for item in items)
        return {
            "items": items,
            "summary": {"fills": len(items), "received": received},
        }

    @router.post("/purchases", status_code=201)
    def purchases(request: PurchaseRequest) -> dict:
        return repository.purchase(
            market_hash_name=request.market_hash_name,
            quantity=request.quantity,
            cost_each=request.cost_each,
            purchased_at=request.purchased_at or int(time.time()),
            venue=request.venue,
            pending_delivery=request.pending_delivery,
        )

    @router.post("/sales", status_code=201)
    def sales(request: SaleRequest) -> dict:
        return repository.sale(
            market_hash_name=request.market_hash_name,
            quantity=request.quantity,
            receive_total=request.receive_total,
            sold_at=request.sold_at or int(time.time()),
        )

    @router.post("/purchases/{pending_id}/receive", status_code=201)
    def receive_purchase(pending_id: str, request: ReceiveRequest) -> dict:
        return repository.receive_pending(
            pending_id=pending_id,
            quantity=request.quantity,
            received_at=request.received_at or int(time.time()),
        )

    @router.get("/pending-purchases")
    def pending_purchases() -> dict:
        items = repository.pending()
        return {"items": items, "summary": {"count": len(items)}}

    @router.get("/ledger/catalog")
    def catalog(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=20, ge=1, le=50),
    ) -> dict:
        return {"items": repository.catalog(q, limit)}

    @router.get("/inventory")
    def inventory() -> dict:
        session = inventory_service.session_status()
        if session.status != "active":
            return {
                "status": "session_required",
                "items": [],
                "groups": [],
                "message": "Steam 会话未连接，暂不能读取单件资产。",
            }
        return {
            "status": "ready",
            "items": inventory_service.list_assets(),
            "groups": inventory_service.list_grouped_assets(),
            "steamid64": session.steamid64,
        }

    @router.get("/inventory/groups/{market_hash_name}/details")
    def inventory_group_details(market_hash_name: str) -> dict:
        details = inventory_service.get_group_details(market_hash_name)
        if details is None:
            raise HTTPException(status_code=404, detail="inventory group not found")
        return details

    @router.post("/inventory/refresh")
    def refresh_inventory() -> dict:
        result = inventory_service.refresh()
        return {
            "run_id": result.run_id,
            "asset_count": result.asset_count,
            "observed_at": result.observed_at,
        }

    @router.get("/platform-health")
    def platform_health() -> dict:
        return {
            "items": [
                {"platform": "csqaq", "status": "configured"},
                {"platform": "buff", "status": "anonymous"},
                {
                    "platform": "steam",
                    "status": (
                        "anonymous_quotes_inventory_ready"
                        if inventory_service.session_status().status == "active"
                        else "anonymous_quotes_session_required_inventory"
                    ),
                },
            ]
        }

    return router
