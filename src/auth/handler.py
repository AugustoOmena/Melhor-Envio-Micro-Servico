"""AWS Lambda handler for Melhor Envio auth endpoints."""

from __future__ import annotations

import json
import os
import secrets
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from auth_schemas import TokenRequest
from auth_service import AuthService
from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import load_config
from shared.melhor_envio_oauth import MelhorEnvioOAuthClient
from shared.supabase import SupabaseConfig, SupabaseRestClient
from shared.token_store import MelhorEnvioTokenStore, TokenStoreError

logger = Logger(service="melhorenvio-auth")
tracer = Tracer(service="melhorenvio-auth")
metrics = Metrics(namespace="MelhorEnvioMicroservice", service="melhorenvio-auth")

app = APIGatewayHttpResolver()

ADMIN_SUBJECT = "admin"


def _build_service() -> AuthService:
    cfg = load_config()
    if not cfg.client_id or not cfg.client_secret:
        raise RuntimeError("Missing MELHOR_ENVIO_CLIENT_ID or MELHOR_ENVIO_CLIENT_SECRET env vars.")
    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    oauth = MelhorEnvioOAuthClient(http=http, config=cfg)
    return AuthService(oauth=oauth, client_id=cfg.client_id, client_secret=cfg.client_secret)


def _build_token_store(http: HttpClient) -> MelhorEnvioTokenStore:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY env vars.")

    sb_cfg = SupabaseConfig(url=supabase_url, service_role_key=supabase_key)
    sb = SupabaseRestClient(http=http, cfg=sb_cfg)
    return MelhorEnvioTokenStore(sb)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/integrations/melhorenvio/status")
def integration_status() -> Response:
    cfg = load_config()
    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    store = _build_token_store(http)

    try:
        rec = store.get(subject=ADMIN_SUBJECT, env=cfg.env)
    except TokenStoreError as e:
        logger.warning("Token store error", extra={"error": str(e)})
        return Response(status_code=502, content_type="application/json", body={"connected": False, "message": "token_store_error"})

    return Response(
        status_code=200,
        content_type="application/json",
        body={
            "connected": rec is not None,
            "env": cfg.env,
            "expires_at": rec.expires_at.isoformat() if rec and rec.expires_at else None,
            "scope": rec.scope if rec else None,
        },
    )


@app.get("/integrations/melhorenvio/authorize-url")
def authorize_url() -> Response:
    cfg = load_config()
    if not cfg.client_id:
        return Response(
            status_code=500,
            content_type="application/json",
            body=json.dumps({"message": "missing_client_id"}),
        )

    qs = app.current_event.query_string_parameters or {}
    redirect_uri = (qs.get("redirect_uri") or cfg.default_redirect_uri or "").strip()
    if not redirect_uri:
        return Response(
            status_code=400,
            content_type="application/json",
            body=json.dumps({"message": "missing_redirect_uri"}),
        )

    scopes_raw = (qs.get("scopes") or "").strip()
    scopes_list = [s.strip() for s in scopes_raw.split(",") if s.strip()] if scopes_raw else list(cfg.default_scopes)

    state = secrets.token_urlsafe(24)
    url = cfg.build_authorize_url(redirect_uri=redirect_uri, scopes=scopes_list, state=state)

    return Response(
        status_code=200,
        content_type="application/json",
        body=json.dumps({"authorize_url": url, "state": state, "redirect_uri": redirect_uri, "scopes": scopes_list}),
    )

CALLBACK_REDIRECT_URI = "https://dev.augustoomena.com/backoffice/integrations/melhorenvio/callback"


@app.get("/integrations/melhorenvio/callback")
@tracer.capture_method
def oauth_callback() -> Response:
    qs = app.current_event.query_string_parameters or {}
    code = (qs.get("code") or "").strip()
    state = (qs.get("state") or "").strip() or None

    if not code:
        return Response(
            status_code=400,
            content_type="application/json",
            body=json.dumps({"message": "missing_code"}),
        )

    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    cfg = load_config()

    try:
        svc = _build_service()
        token = svc.create_token(
            TokenRequest.model_validate(
                {"grant_type": "authorization_code", "code": code, "redirect_uri": CALLBACK_REDIRECT_URI}
            )
        )

        store = _build_token_store(http)
        rec = store.upsert_from_token_response(subject=ADMIN_SUBJECT, env=cfg.env, token_response=token)
        metrics.add_metric(name="AuthCallbackSuccess", unit=MetricUnit.Count, value=1)
        return Response(
            status_code=200,
            content_type="application/json",
            body=json.dumps({
                "connected": True,
                "env": cfg.env,
                "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
                "scope": rec.scope,
                "state": state,
            }),
        )
    except ValidationError as e:
        metrics.add_metric(name="AuthCallbackValidationError", unit=MetricUnit.Count, value=1)
        return Response(
            status_code=400,
            content_type="application/json",
            body=json.dumps({"message": "invalid_request", "errors": e.errors()}),
        )
    except TokenStoreError as e:
        metrics.add_metric(name="AuthCallbackTokenStoreError", unit=MetricUnit.Count, value=1)
        logger.warning("Token store error", extra={"error": str(e)})
        return Response(
            status_code=502,
            content_type="application/json",
            body=json.dumps({"message": "token_store_error"}),
        )
    except HttpClientError as e:
        metrics.add_metric(name="AuthCallbackUpstreamError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Upstream token error",
            extra={"status_code": e.status_code, "response_body": e.response_body},
        )
        return Response(
            status_code=502,
            content_type="application/json",
            body=json.dumps({
                "message": "upstream_error",
                "status_code": e.status_code,
                "details": e.response_body,
            }),
        )
    except Exception:
        metrics.add_metric(name="AuthCallbackUnhandledError", unit=MetricUnit.Count, value=1)
        logger.exception("Unhandled error processing oauth callback")
        return Response(
            status_code=500,
            content_type="application/json",
            body=json.dumps({"message": "internal_error"}),
        )


@app.post("/auth/token")
@tracer.capture_method
def create_token() -> Response:
    try:
        payload = app.current_event.json_body or {}
        req = TokenRequest.model_validate(payload)
    except ValidationError as e:
        metrics.add_metric(name="AuthTokenValidationError", unit=MetricUnit.Count, value=1)
        return Response(status_code=400, content_type="application/json", body={"message": "invalid_request", "errors": e.errors()})

    try:
        svc = _build_service()
        token = svc.create_token(req)
        metrics.add_metric(name="AuthTokenSuccess", unit=MetricUnit.Count, value=1)
        return Response(status_code=200, content_type="application/json", body=token)
    except HttpClientError as e:
        metrics.add_metric(name="AuthTokenUpstreamError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Upstream token error",
            extra={"status_code": e.status_code, "response_body": e.response_body},
        )
        return Response(
            status_code=502,
            content_type="application/json",
            body={"message": "upstream_error", "status_code": e.status_code, "details": e.response_body},
        )
    except Exception:
        metrics.add_metric(name="AuthTokenUnhandledError", unit=MetricUnit.Count, value=1)
        logger.exception("Unhandled error creating token")
        return Response(status_code=500, content_type="application/json", body={"message": "internal_error"})


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)

