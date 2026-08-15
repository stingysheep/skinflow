import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from skinflow_api.application.scan.upstream_errors import RateLimited, UpstreamUnavailable


@dataclass(frozen=True, slots=True)
class HttpClient:
    timeout: float = 15.0
    user_agent: str = "Skinflow/0.1"

    def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict | None = None,
    ) -> dict:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request_headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        request_headers.update(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            retry_after = error.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            if error.code == 429:
                raise RateLimited(retry_after_seconds=retry_seconds) from error
            raise UpstreamUnavailable(
                f"upstream status {error.code}", status_code=error.code
            ) from error
        except (TimeoutError, urllib.error.URLError) as error:
            raise UpstreamUnavailable(type(error).__name__) from error

    def request_form(
        self,
        url: str,
        fields: dict[str, str],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        payload = urllib.parse.urlencode(fields).encode("utf-8")
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        request_headers.update(headers or {})
        request = urllib.request.Request(url, data=payload, headers=request_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            retry_after = error.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            if error.code == 429:
                raise RateLimited(retry_after_seconds=retry_seconds) from error
            raise UpstreamUnavailable(
                f"upstream status {error.code}", status_code=error.code
            ) from error
        except (TimeoutError, urllib.error.URLError) as error:
            raise UpstreamUnavailable(type(error).__name__) from error
