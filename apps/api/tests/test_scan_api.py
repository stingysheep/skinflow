from fastapi import FastAPI
from fastapi.testclient import TestClient

from skinflow_api.application.scan.memory_uow import InMemoryScanUnitOfWork
from skinflow_api.application.scan.service import ScanService
from skinflow_api.routes.errors import install_error_handlers
from skinflow_api.routes.scan import ScanCreateBody, create_scan_router


class EmptyCandidates:
    def list_candidates(self, request, event_sink=None):
        return ()


class NoNameIds:
    def resolve(self, market_hash_name):
        return None


class NoMarket:
    def fetch_snapshot(self, candidate, item_nameid):
        raise AssertionError("no market request expected")


class ImmediateRunner:
    def __init__(self, service):
        self._service = service

    def start(self, job_id):
        self._service.run(job_id)


def client() -> TestClient:
    persistence = InMemoryScanUnitOfWork()
    service = ScanService(persistence, EmptyCandidates(), NoNameIds(), NoMarket())
    app = FastAPI()
    app.include_router(create_scan_router(service, ImmediateRunner(service)))
    install_error_handlers(app)
    return TestClient(app)


def test_scan_create_and_event_resume_contract() -> None:
    with client() as api:
        response = api.post(
            "/api/scans",
            json={"source_mode": "csqaq", "candidate_limit": 2, "manual_names": []},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        events = api.get(f"/api/scans/{job_id}/events").json()
        resumed = api.get(f"/api/scans/{job_id}/events?after=1").json()

    assert events[0]["schema_version"] == 1
    assert all(event["sequence"] > 1 for event in resumed)


def test_scan_rejects_invalid_input_limits() -> None:
    with client() as api:
        response = api.post(
            "/api/scans",
            json={"source_mode": "csqaq", "candidate_limit": 201, "manual_names": []},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_scan_results_and_structured_not_found_contract() -> None:
    with client() as api:
        missing = api.get("/api/scans/missing/results")
        response = api.post(
            "/api/scans",
            json={"source_mode": "manual", "candidate_limit": 1, "manual_names": ["ＡＫ"]},
        )
        results = api.get(f"/api/scans/{response.json()['job_id']}/results")

    assert results.json() == {"items": []}
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SCAN_NOT_FOUND"
    assert missing.json()["error"]["correlation_id"]


def test_manual_names_are_unicode_normalized_and_deduplicated() -> None:
    body = ScanCreateBody(
        source_mode="manual",
        candidate_limit=2,
        manual_names=["ＡＫ－４７", "AK-47"],
    )
    assert body.manual_names == ["AK-47"]
