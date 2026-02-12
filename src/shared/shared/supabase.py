"""Supabase REST client (PostgREST) using standard library HTTP.

This module intentionally avoids heavy dependencies to keep Lambda cold starts low.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from shared.http import HttpClient, HttpClientError


class SupabaseError(Exception):
    """Raised when a Supabase REST call fails."""


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_role_key: str

    @property
    def rest_base_url(self) -> str:
        return f"{self.url.rstrip('/')}/rest/v1"


class SupabaseRestClient:
    """Minimal PostgREST client for Supabase."""

    def __init__(self, http: HttpClient, cfg: SupabaseConfig) -> None:
        self._http = http
        self._cfg = cfg

    def get(self, path: str, *, query: str = "", headers: Mapping[str, str] | None = None) -> Any:
        url = f"{self._cfg.rest_base_url}/{path.lstrip('/')}{query}"
        return self._request_json("GET", url, headers=headers)

    def post(self, path: str, *, json_body: Any, headers: Mapping[str, str] | None = None) -> Any:
        url = f"{self._cfg.rest_base_url}/{path.lstrip('/')}"
        return self._request_json("POST", url, headers=headers, json_body=json_body)

    def patch(self, path: str, *, query: str = "", json_body: Any, headers: Mapping[str, str] | None = None) -> Any:
        url = f"{self._cfg.rest_base_url}/{path.lstrip('/')}{query}"
        return self._request_json("PATCH", url, headers=headers, json_body=json_body)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        final_headers = {
            "apikey": self._cfg.service_role_key,
            "Authorization": f"Bearer {self._cfg.service_role_key}",
            **dict(headers or {}),
        }
        try:
            resp = self._http.request_json(method, url, headers=final_headers, json_body=json_body)
            return resp.body
        except HttpClientError as e:
            raise SupabaseError(f"Supabase REST error: {e.status_code} {e.response_body}") from e

