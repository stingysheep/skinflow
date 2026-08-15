from __future__ import annotations

from skinflow_api.application.listing.models import ListingGatewayResult
from skinflow_api.application.scan.upstream_errors import UpstreamUnavailable
from skinflow_api.infrastructure.http.client import HttpClient

from .session import InMemorySteamSession

SELL_URL = "https://steamcommunity.com/market/sellitem/"
CANCEL_URL = "https://steamcommunity.com/market/removelisting/"


class SteamListingAdapter:
    """Submits exactly one Steam sell request and never confirms or retries it."""

    def __init__(self, session: InMemorySteamSession, client: HttpClient | None = None) -> None:
        self._session = session
        self._client = client or HttpClient()

    def submit(self, decision: dict) -> ListingGatewayResult:
        credentials = self._session.credentials()
        steam_price = _seller_receive_price(decision)
        try:
            response = self._client.request_form(
                SELL_URL,
                {
                    "sessionid": credentials.sessionid,
                    "appid": str(decision["appid"]),
                    "contextid": str(decision["contextid"]),
                    "assetid": str(decision["assetid"]),
                    "amount": "1",
                    # Steam's sellitem endpoint expects the seller-receives
                    # amount; buyer_pays is the derived market-facing total.
                    "price": steam_price,
                },
                headers={
                    "Cookie": credentials.cookie_header,
                    "Referer": (
                        f"https://steamcommunity.com/profiles/{credentials.steamid64}/inventory/"
                    ),
                },
            )
        except UpstreamUnavailable as error:
            if error.status_code in {401, 403}:
                self._session.mark_expired()
                raise PermissionError("Steam session expired") from error
            raise
        return ListingGatewayResult(
            accepted=bool(response.get("success")),
            needs_confirmation=bool(response.get("requires_confirmation")),
            listing_id=(str(response["listingid"]) if response.get("listingid") else None),
            message=str(response.get("message") or "") or None,
        )
    def cancel(self, listing_id: str) -> bool:
        credentials = self._session.credentials()
        try:
            response = self._client.request_form(
                f"{CANCEL_URL}{listing_id}",
                {"sessionid": credentials.sessionid},
                headers={
                    "Cookie": credentials.cookie_header,
                    "Referer": "https://steamcommunity.com/market/",
                },
            )
        except UpstreamUnavailable as error:
            if error.status_code in {401, 403}:
                self._session.mark_expired()
                raise PermissionError("Steam session expired") from error
            raise
        return bool(response.get("success"))


def _seller_receive_price(decision: dict) -> str:
    """Return the integer fen Steam expects for ``sellitem.price``.

    The endpoint does not accept the buyer-paid total. Keeping this conversion
    at the adapter boundary makes an accidental field swap fail immediately
    instead of creating a listing at a different market price.
    """

    value = decision.get("seller_proceeds")
    if isinstance(value, bool):
        raise ValueError("seller_proceeds must be an integer fen amount")
    try:
        price = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("seller_proceeds must be an integer fen amount") from error
    if price < 1:
        raise ValueError("seller_proceeds must be positive")
    return str(price)
