"""Token persistence for Melhor Envio using Supabase PostgREST."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from shared.supabase import SupabaseRestClient


class TokenStoreError(Exception):
    """Raised when reading/writing tokens fails."""


@dataclass(frozen=True)
class MelhorEnvioTokenRecord:
    subject: str
    env: str
    access_token: str
    refresh_token: str | None
    token_type: str
    scope: str | None
    expires_at: dt.datetime | None


class MelhorEnvioTokenStore:
    """Persist Melhor Envio OAuth tokens in Supabase."""

    def __init__(self, supabase: SupabaseRestClient, *, table: str = "melhor_envio_oauth_tokens") -> None:
        self._supabase = supabase
        self._table = table

    def get(self, *, subject: str, env: str) -> MelhorEnvioTokenRecord | None:
        query = f"?subject=eq.{subject}&env=eq.{env}&select=subject,env,access_token,refresh_token,token_type,scope,expires_at&limit=1"
        rows = self._supabase.get(self._table, query=query)
        if not rows:
            return None
        if not isinstance(rows, list) or not isinstance(rows[0], dict):
            raise TokenStoreError("Unexpected Supabase response shape for token get.")
        row = rows[0]
        return MelhorEnvioTokenRecord(
            subject=str(row["subject"]),
            env=str(row["env"]),
            access_token=str(row["access_token"]),
            refresh_token=row.get("refresh_token"),
            token_type=str(row.get("token_type") or "Bearer"),
            scope=row.get("scope"),
            expires_at=_parse_dt(row.get("expires_at")),
        )

    def upsert_from_token_response(
        self,
        *,
        subject: str,
        env: str,
        token_response: dict[str, Any],
    ) -> MelhorEnvioTokenRecord:
        access_token = str(token_response.get("access_token") or "")
        if not access_token:
            raise TokenStoreError("Missing access_token in token response.")

        refresh_token = token_response.get("refresh_token")
        token_type = str(token_response.get("token_type") or "Bearer")
        scope = token_response.get("scope")

        expires_at = _compute_expires_at(token_response.get("expires_in"))

        payload = {
            "subject": subject,
            "env": env,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token_type,
            "scope": scope,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }

        # Upsert using unique(subject, env)
        rows = self._supabase.post(
            self._table,
            json_body=payload,
            headers={
                "Prefer": "resolution=merge-duplicates,return=representation",
                "Content-Type": "application/json",
            },
        )

        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            # Some PostgREST configs might not return representation; fallback to get.
            rec = self.get(subject=subject, env=env)
            if rec is None:
                raise TokenStoreError("Upsert did not return a token record and subsequent get returned none.")
            return rec

        row = rows[0]
        return MelhorEnvioTokenRecord(
            subject=str(row.get("subject") or subject),
            env=str(row.get("env") or env),
            access_token=str(row.get("access_token") or access_token),
            refresh_token=row.get("refresh_token", refresh_token),
            token_type=str(row.get("token_type") or token_type),
            scope=row.get("scope", scope),
            expires_at=_parse_dt(row.get("expires_at")) or expires_at,
        )


def _parse_dt(value: Any) -> dt.datetime | None:
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        # Supabase returns ISO 8601 with timezone (e.g., 2026-02-12T10:00:00+00:00)
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def _compute_expires_at(expires_in: Any) -> dt.datetime | None:
    if expires_in is None:
        return None
    try:
        v = int(expires_in)
    except (TypeError, ValueError):
        return None

    now = dt.datetime.now(tz=dt.timezone.utc)
    # If it's a unix timestamp (seconds since epoch)
    if v > 1_000_000_000:
        try:
            return dt.datetime.fromtimestamp(v, tz=dt.timezone.utc)
        except (OverflowError, OSError):
            return None
    # Otherwise treat as seconds until expiration
    if v <= 0:
        return None
    return now + dt.timedelta(seconds=v)

