class UpstreamError(RuntimeError):
    code = "UPSTREAM_UNAVAILABLE"


class RateLimited(UpstreamError):
    code = "UPSTREAM_RATE_LIMITED"

    def __init__(
        self,
        message: str = "upstream rate limited",
        *,
        retry_after_seconds: int | None = None,
        platform: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.platform = platform


class UpstreamUnavailable(UpstreamError):
    code = "UPSTREAM_UNAVAILABLE"

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CsqaqAccessDenied(UpstreamError):
    code = "CSQAQ_ACCESS_DENIED"
