import asyncio
import json
import unicodedata
from collections.abc import AsyncIterator
from typing import Literal, Protocol

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from skinflow_api.application.scan.models import AcquisitionPlatform, ScanMode, ScanRequest
from skinflow_api.application.scan.service import ScanService

from .errors import error_response


class ScanRunner(Protocol):
    def start(self, job_id: str) -> None: ...


class ScanCreateBody(BaseModel):
    source_mode: Literal["csqaq", "manual", "hybrid"] = "csqaq"
    manual_names: list[str] = Field(default_factory=list, max_length=200)
    candidate_limit: int = Field(default=20, ge=1, le=200)
    operation_mode: Literal["listing", "buy_order"] = "listing"
    acquisition_platforms: list[Literal["buff", "youpin"]] = Field(
        default_factory=lambda: ["buff"], min_length=1, max_length=2
    )
    min_price: int | None = Field(default=None, ge=1, le=100_000_000)
    max_price: int | None = Field(default=None, ge=1, le=100_000_000)
    min_daily_volume: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("manual_names")
    @classmethod
    def validate_names(cls, names: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for name in names:
            value = " ".join(unicodedata.normalize("NFKC", name).split())
            if not value or len(value) > 200:
                raise ValueError("manual_names must be non-empty and <= 200 characters")
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        return normalized

    @field_validator("acquisition_platforms")
    @classmethod
    def validate_platforms(cls, platforms: list[str]) -> list[str]:
        return list(dict.fromkeys(platforms))


def create_scan_router(service: ScanService, runner: ScanRunner) -> APIRouter:
    router = APIRouter(prefix="/api/scans", tags=["scans"])

    @router.post("")
    async def create_scan(body: ScanCreateBody):
        try:
            job = service.create(
                ScanRequest(
                    source_mode=body.source_mode,
                    candidate_limit=body.candidate_limit,
                    manual_names=tuple(body.manual_names),
                    operation_mode=ScanMode(body.operation_mode),
                    acquisition_platforms=tuple(
                        AcquisitionPlatform(platform)
                        for platform in body.acquisition_platforms
                    ),
                    min_price=body.min_price,
                    max_price=body.max_price,
                    min_daily_volume=body.min_daily_volume,
                )
            )
        except ValueError as error:
            return error_response(
                409,
                "SCAN_ALREADY_ACTIVE",
                str(error),
                retryable=True,
            )
        runner.start(job.id)
        return {"job_id": job.id, "status": job.status}

    @router.get("/{job_id}")
    async def get_scan(job_id: str):
        job = service.get(job_id)
        if job is None:
            return _not_found()
        return {
            "job_id": job.id,
            "status": job.status,
            "result_count": job.result_count,
            "failure_code": job.failure_code,
        }

    @router.post("/{job_id}/cancel")
    async def cancel_scan(job_id: str):
        try:
            job = service.cancel(job_id)
        except LookupError:
            return _not_found()
        return {"job_id": job.id, "status": job.status}

    @router.get("/{job_id}/events")
    async def get_events(
        job_id: str,
        after: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None),
    ):
        if service.get(job_id) is None:
            return _not_found()
        cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after
        return service.events(job_id, cursor)

    @router.get("/{job_id}/results")
    async def get_results(job_id: str):
        try:
            return {"items": service.results(job_id)}
        except LookupError:
            return _not_found()

    @router.get("/{job_id}/results/{market_hash_name}/charts")
    async def get_result_charts(
        job_id: str,
        market_hash_name: str,
        platforms: str = Query(default="steam,buff"),
    ):
        requested = tuple(value for value in platforms.split(",") if value)
        try:
            trends = service.charts(job_id, market_hash_name, requested)
        except LookupError:
            return _not_found()
        return {
            "market_hash_name": market_hash_name,
            "trends": {
                platform: [
                    {
                        "observed_at": point.get("observed_at"),
                        "price": point.get("value"),
                        "quantity": point.get("quantity"),
                    }
                    for point in points
                ]
                for platform, points in trends.items()
            },
        }

    @router.get("/{job_id}/stream")
    async def stream_events(
        request: Request,
        job_id: str,
        after: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None),
    ):
        if service.get(job_id) is None:
            return _not_found()
        cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

        async def events() -> AsyncIterator[str]:
            current = cursor
            while True:
                if await request.is_disconnected():
                    return
                batch = service.events(job_id, current)
                for event in batch:
                    current = event["sequence"]
                    data = json.dumps(event, ensure_ascii=False)
                    yield f"id: {current}\nevent: {event['type']}\ndata: {data}\n\n"
                job = service.get(job_id)
                if job is None:
                    return
                if job.status.value in {"cancelled", "succeeded", "failed"} and not batch:
                    return
                await asyncio.sleep(0.25)

        return StreamingResponse(events(), media_type="text/event-stream")

    return router


def _not_found() -> JSONResponse:
    return error_response(404, "SCAN_NOT_FOUND", "scan not found")
