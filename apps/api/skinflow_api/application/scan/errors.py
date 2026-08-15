class ScanConfigurationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class NameIdIndexUnavailable(ScanConfigurationError):
    def __init__(self) -> None:
        super().__init__("NAMEID_INDEX_UNAVAILABLE")


class NameIdIndexInvalid(ScanConfigurationError):
    def __init__(self) -> None:
        super().__init__("NAMEID_INDEX_INVALID")
