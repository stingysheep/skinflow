class LoginUnavailable(RuntimeError):
    """The local desktop login surface is not available in this runtime."""


class InventoryError(RuntimeError):
    code = "INVENTORY_UNAVAILABLE"


class InventoryRateLimited(InventoryError):
    code = "STEAM_INVENTORY_RATE_LIMITED"

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        super().__init__("Steam 库存请求过于频繁，请稍后重试")
        self.retry_after_seconds = retry_after_seconds


class InventoryUnavailable(InventoryError):
    code = "STEAM_INVENTORY_UNAVAILABLE"


class SteamSessionExpired(PermissionError):
    code = "STEAM_SESSION_EXPIRED"
