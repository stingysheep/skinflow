import pytest

from skinflow_api.domain.money import Money
from skinflow_api.domain.money.errors import InvalidMoney
from skinflow_api.domain.pricing import (
    Tier,
    build_price_curves,
    calculate_net,
    expand_tiers,
    receive_to_pays,
    recommend_listing_price,
    steam_cny_policy,
)
from skinflow_api.domain.pricing.errors import BelowMinimumPrice, UnsupportedFeePolicy


def test_money_is_integer_cny() -> None:
    assert Money(112).amount_minor == 112
    with pytest.raises(InvalidMoney):
        Money(1, "USD")


def test_steam_fee_rounds_each_fee_down_and_is_reversible() -> None:
    policy = steam_cny_policy()
    breakdown = receive_to_pays(100, policy)
    assert breakdown.steam_fee == 5
    assert breakdown.publisher_fee == 10
    assert breakdown.buyer_pays == 115
    assert calculate_net(115, policy).seller_proceeds == 100


def test_low_price_buyer_total_maps_to_steam_seller_price() -> None:
    policy = steam_cny_policy()

    breakdown = calculate_net(34, policy)

    assert breakdown.buyer_pays == 34
    assert breakdown.steam_fee == 5
    assert breakdown.publisher_fee == 5
    assert breakdown.seller_proceeds == 24


def test_low_price_seller_amount_uses_cny_minimum_fee() -> None:
    breakdown = receive_to_pays(34, steam_cny_policy())

    assert breakdown.buyer_pays == 44
    assert breakdown.steam_fee == 5
    assert breakdown.publisher_fee == 5


def test_non_cny_policy_is_rejected() -> None:
    with pytest.raises(UnsupportedFeePolicy):
        steam_cny_policy(currency="USD")


def test_tiers_expand_in_order_and_stop_at_depth_limit() -> None:
    tiers = (Tier(112, 3), Tier(113, 5), Tier(116, 2))
    assert expand_tiers(tiers, limit=10) == (112, 112, 112, 113, 113, 113, 113, 113, 116, 116)


def test_curves_return_null_when_depth_is_short() -> None:
    policy = steam_cny_policy()
    points = build_price_curves(
        (Tier(112, 2),), (Tier(223, 1),), (Tier(224, 2),), policy, limit=2
    )
    assert points[0].immediate_ratio_ppm is not None
    assert points[1].immediate_ratio_ppm is None


def test_recommendation_calculates_queue_and_eta() -> None:
    policy = steam_cny_policy()
    estimate = recommend_listing_price(
        lowest_ask=224,
        price_tick=1,
        fee_policy=policy,
        requested_qty=2,
        ask_levels=(Tier(200, 3), Tier(223, 4)),
        min_price=100,
        daily_volume=10,
    )
    assert estimate.recommended_price <= 223
    assert estimate.queue_ahead == 7
    assert estimate.eta_estimate == 0.9
    assert estimate.fee_policy_version == "steam-cs2-cny-v2-min5"


def test_recommendation_below_minimum_does_not_silent_adjust() -> None:
    with pytest.raises(BelowMinimumPrice):
        recommend_listing_price(
            lowest_ask=101,
            price_tick=1,
            fee_policy=steam_cny_policy(),
            requested_qty=1,
            ask_levels=(),
            min_price=101,
            daily_volume=None,
        )
