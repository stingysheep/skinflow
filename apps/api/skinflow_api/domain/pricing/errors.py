class UnsupportedFeePolicy(ValueError):
    """No fee rule exists for the requested app and currency."""


class UnreachablePrice(ValueError):
    """The target buyer-paid price cannot be produced by the fee policy."""


class BelowMinimumPrice(ValueError):
    """A recommended price would violate the configured minimum."""


class NegativeProceeds(ValueError):
    """A fee calculation would produce negative seller proceeds."""
