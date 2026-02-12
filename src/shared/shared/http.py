"""HTTP utilities using only the Python standard library.

We intentionally avoid heavyweight HTTP dependencies to reduce Lambda cold starts.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class HttpClientError(Exception):
    """Raised when an HTTP request fails."""

    def __init__(self, status_code: int | None, message: str, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: Any
    raw_body: str


class HttpClient:
    """Small HTTP client wrapper to improve testability."""

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self._timeout_seconds = timeout_seconds

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        if json_body is not None and data is not None:
            raise ValueError("Provide either json_body or data, not both.")

        final_headers: dict[str, str] = dict(headers or {})

        payload: bytes | None = data
        if json_body is not None:
            payload = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            final_headers.setdefault("Content-Type", "application/json")

        final_headers.setdefault("Accept", "application/json")

        req = urllib.request.Request(url=url, data=payload, method=method.upper(), headers=final_headers)

        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:  # nosec B310
                raw = resp.read().decode("utf-8", errors="replace")
                return HttpResponse(
                    status_code=int(getattr(resp, "status", 200)),
                    headers={k: v for k, v in resp.headers.items()},
                    body=_maybe_json(raw),
                    raw_body=raw,
                )
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if getattr(e, "fp", None) is not None else ""
            raise HttpClientError(
                status_code=int(getattr(e, "code", 0) or 0) or None,
                message=f"HTTP {getattr(e, 'code', 'error')} calling {url}",
                response_body=raw or None,
            ) from e
        except urllib.error.URLError as e:
            raise HttpClientError(status_code=None, message=f"Network error calling {url}: {e}") from e


def _maybe_json(raw: str) -> Any:
    raw_stripped = raw.strip()
    if not raw_stripped:
        return None
    try:
        return json.loads(raw_stripped)
    except json.JSONDecodeError:
        return raw

