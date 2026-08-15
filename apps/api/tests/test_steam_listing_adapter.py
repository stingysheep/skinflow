from skinflow_api.application.listing.models import ListingGatewayResult
from skinflow_api.infrastructure.platforms.steam.listing import (
    SteamListingAdapter,
    _seller_receive_price,
)
from skinflow_api.infrastructure.platforms.steam.session import (
    InMemorySteamSession,
    SteamCredentials,
)


class Client:
    def __init__(self):
        self.fields = None

    def request_form(self, _url, fields, *, headers=None):
        self.fields = fields
        return {"success": True, "listingid": "listing-1"}


def test_submit_sends_seller_proceeds_price_to_steam() -> None:
    session = InMemorySteamSession()
    session.set_credentials(SteamCredentials("76561198000000000", "secure", "session"))
    client = Client()
    result = SteamListingAdapter(session, client).submit({
        "appid": 730,
        "contextid": "2",
        "assetid": "asset-1",
        "buyer_pays": 31,
        "seller_proceeds": 24,
    })

    assert isinstance(result, ListingGatewayResult)
    # Steam's sellitem endpoint accepts the seller-receives amount. The
    # buyer-paid amount is calculated by Steam after fees are applied.
    assert client.fields["price"] == "24"


def test_steam_price_boundary_rejects_missing_or_non_positive_receive_amount() -> None:
    import pytest

    with pytest.raises(ValueError, match="seller_proceeds"):
        _seller_receive_price({"buyer_pays": 31})
    with pytest.raises(ValueError, match="positive"):
        _seller_receive_price({"seller_proceeds": 0})


def test_cancel_uses_steam_remove_listing_endpoint() -> None:
    session = InMemorySteamSession()
    session.set_credentials(SteamCredentials("76561198000000000", "secure", "session"))
    client = Client()
    assert SteamListingAdapter(session, client).cancel("listing-2") is True
    assert client.fields == {"sessionid": "session"}
