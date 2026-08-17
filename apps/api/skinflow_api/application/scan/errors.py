class ScanConfigurationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CsqaqConfigurationError(ScanConfigurationError):
    def __init__(self, status: str) -> None:
        codes = {
            "missing": "CSQAQ_TOKEN_REQUIRED",
            "access_denied": "CSQAQ_ACCESS_DENIED",
            "rate_limited": "CSQAQ_UNAVAILABLE",
            "unavailable": "CSQAQ_UNAVAILABLE",
        }
        super().__init__(codes.get(status, "CSQAQ_UNAVAILABLE"))


class NameIdIndexUnavailable(ScanConfigurationError):
    def __init__(self) -> None:
        super().__init__("NAMEID_INDEX_UNAVAILABLE")


class NameIdIndexInvalid(ScanConfigurationError):
    def __init__(self) -> None:
        super().__init__("NAMEID_INDEX_INVALID")
