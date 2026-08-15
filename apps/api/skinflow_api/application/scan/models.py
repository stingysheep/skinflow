from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ScanMode(StrEnum):
    LISTING = "listing"
    BUY_ORDER = "buy_order"


class AcquisitionPlatform(StrEnum):
    BUFF = "buff"
    YOUPIN = "youpin"


@dataclass(frozen=True, slots=True)
class ScanRequest:
    source_mode: str
    candidate_limit: int
    manual_names: tuple[str, ...] = ()
    depth_limit_per_candidate: int = 10
    operation_mode: ScanMode = ScanMode.LISTING
    acquisition_platforms: tuple[AcquisitionPlatform, ...] = (AcquisitionPlatform.BUFF,)
    min_price: int | None = None
    max_price: int | None = None
    min_daily_volume: int = 0

    def __post_init__(self) -> None:
        if self.source_mode not in {"csqaq", "manual", "hybrid"}:
            raise ValueError("source_mode must be csqaq, manual or hybrid")
        if not 1 <= self.candidate_limit <= 200:
            raise ValueError("candidate_limit must be between 1 and 200")
        if len(self.manual_names) > 200:
            raise ValueError("manual_names cannot contain more than 200 names")
        if self.depth_limit_per_candidate != 10:
            raise ValueError("depth_limit_per_candidate is fixed at 10")
        if any(not name or len(name) > 200 for name in self.manual_names):
            raise ValueError("manual names must be non-empty and <= 200 characters")
        if not self.acquisition_platforms:
            raise ValueError("at least one acquisition platform is required")
        if len(set(self.acquisition_platforms)) != len(self.acquisition_platforms):
            raise ValueError("acquisition platforms must be unique")
        if any(platform not in AcquisitionPlatform for platform in self.acquisition_platforms):
            raise ValueError("unsupported acquisition platform")
        if self.min_price is not None and self.min_price < 1:
            raise ValueError("min_price must be positive")
        if self.max_price is not None and self.max_price < 1:
            raise ValueError("max_price must be positive")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot exceed max_price")
        if not 0 <= self.min_daily_volume <= 1_000_000:
            raise ValueError("min_daily_volume must be between 0 and 1000000")


@dataclass(slots=True)
class ScanJob:
    request: ScanRequest
    id: str = field(default_factory=lambda: str(uuid4()))
    status: ScanStatus = ScanStatus.QUEUED
    next_sequence: int = 1
    result_count: int = 0
    failure_code: str | None = None

    def transition(self, target: ScanStatus, failure_code: str | None = None) -> None:
        allowed = {
            ScanStatus.QUEUED: {ScanStatus.RUNNING, ScanStatus.CANCELLED},
            ScanStatus.RUNNING: {ScanStatus.CANCELLING, ScanStatus.SUCCEEDED, ScanStatus.FAILED},
            ScanStatus.CANCELLING: {ScanStatus.CANCELLED},
            ScanStatus.CANCELLED: set(),
            ScanStatus.SUCCEEDED: set(),
            ScanStatus.FAILED: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(f"invalid scan transition {self.status} -> {target}")
        self.status = target
        self.failure_code = failure_code
