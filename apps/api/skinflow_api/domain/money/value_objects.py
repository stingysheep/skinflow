from dataclasses import dataclass

from .errors import InvalidMoney

CNY = "CNY"


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: str = CNY

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise InvalidMoney("amount_minor must be an integer")
        if self.amount_minor < 0:
            raise InvalidMoney("amount_minor cannot be negative")
        if self.currency != CNY:
            raise InvalidMoney(f"unsupported currency {self.currency!r}")
