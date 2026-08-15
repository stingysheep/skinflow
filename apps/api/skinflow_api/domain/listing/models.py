from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListingDecision:
    platform: str
    appid: int
    contextid: str
    assetid: str
    market_hash_name: str
    snapshot_id: str
    snapshot_job_id: str
    buyer_pays: int
    steam_fee: int
    publisher_fee: int
    seller_proceeds: int
    cost_each: int | None
    ratio_ppm: int | None
    fee_policy_version: str


@dataclass(frozen=True, slots=True)
class ListingSubmissionResult:
    status: str
    listing_id: str | None = None
    message: str | None = None
