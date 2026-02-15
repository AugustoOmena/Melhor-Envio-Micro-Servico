"""AWS Lambda handler for Melhor Envio auth endpoints.

Roteamento manual por rawPath/path para diagnóstico e CORS explícito (Proxy Integration v2.0).
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.parse
from typing import Any

DEFAULT_SCOPES = [
    "shipping-calculate",
    "shipping-info",
    "shipping-checkout",
    "shipping-label",
    "shipping-orders",
]

from pydantic import ValidationError

from auth_schemas import TokenRequest
from auth_service import AuthService
from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import load_config
from shared.melhor_envio_oauth import MelhorEnvioOAuthClient
from shared.supabase import SupabaseConfig, SupabaseRestClient
from shared.token_store import MelhorEnvioTokenStore, TokenStoreError

ADMIN_SUBJECT = "admin"
CALLBACK_REDIRECT_URI = "https://dev.augustoomena.com/backoffice/integrations/melhorenvio/callback"

# Headers consistentes para evitar bloqueio do navegador
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Content-Type": "application/json",
}


def _proxy_response(status_code: int, body: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Encapsula a resposta no formato exigido pelo API Gateway Proxy Integration."""
    h = {**CORS_HEADERS, **(headers or {})}
    return {"statusCode": status_code, "headers": h, "body": body}


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


def _handle_health() -> dict[str, Any]:
    return _proxy_response(200, json.dumps({"status": "ok"}))


def _handle_status() -> dict[str, Any]:
    cfg = load_config()
    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    store = _build_token_store(http)
    try:
        rec = store.get(subject=ADMIN_SUBJECT, env=cfg.env)
    except Exception as e:
        print(f"Error fetching token: {e}")
        return _proxy_response(502, json.dumps({"connected": False, "message": "token_store_error"}))
    
    return _proxy_response(
        200,
        json.dumps({
            "connected": rec is not None,
            "env": cfg.env,
            "expires_at": rec.expires_at.isoformat() if rec and rec.expires_at else None,
            "scope": rec.scope if rec else None,
        }),
    )


def _handle_authorize_url(event: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    if not cfg.client_id:
        return _proxy_response(500, json.dumps({"message": "missing_client_id"}))

    qs = event.get("queryStringParameters") or {}
    redirect_uri = (qs.get("redirect_uri") or "").strip() or CALLBACK_REDIRECT_URI

    scopes_raw = (qs.get("scopes") or "").strip()
    scopes_list = [s.strip() for s in scopes_raw.split(",") if s.strip()] if scopes_raw else list(cfg.default_scopes)
    if not scopes_list:
        scopes_list = DEFAULT_SCOPES

    state = secrets.token_urlsafe(24)

    # Montagem manual da URL: scope como string única com espaços codificados em %20 (não +)
    base_url = cfg.base_url
    authorize_base = f"{base_url}/oauth/authorize"
    scope_str = " ".join(scopes_list)
    query_params = {
        "response_type": "code",
        "client_id": cfg.client_id or "",
        "redirect_uri": redirect_uri,
        "scope": scope_str,
        "state": state,
    }
    query_string = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)
    url = f"{authorize_base}?{query_string}"

    print(f"AUTHORIZE_URL_GERADA: {url}")

    return _proxy_response(
        200,
        json.dumps({
            "authorize_url": url,
            "state": state,
            "redirect_uri": redirect_uri,
            "scopes": scopes_list,
        }),
    )


def _handle_callback(event: dict[str, Any]) -> dict[str, Any]:
    qs = event.get("queryStringParameters") or {}
    code = (qs.get("code") or "").strip()
    state = (qs.get("state") or "").strip() or None

    if not code:
        return _proxy_response(400, json.dumps({"message": "missing_code"}))

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
        return _proxy_response(
            200,
            json.dumps({
                "connected": True,
                "env": cfg.env,
                "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
                "scope": rec.scope,
                "state": state,
            }),
        )
    except ValidationError as e:
        return _proxy_response(400, json.dumps({"message": "invalid_request", "errors": e.errors()}))
    except TokenStoreError:
        return _proxy_response(502, json.dumps({"message": "token_store_error"}))
    except HttpClientError as e:
        return _proxy_response(
            502,
            json.dumps({"message": "upstream_error", "status_code": e.status_code, "details": e.response_body}),
        )
    except Exception as e:
        print(f"Internal error in callback: {e}")
        return _proxy_response(500, json.dumps({"message": "internal_error"}))


def _handle_auth_token(event: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(event.get("body") or "{}")
        req = TokenRequest.model_validate(payload)
    except ValidationError as e:
        return _proxy_response(400, json.dumps({"message": "invalid_request", "errors": e.errors()}))

    try:
        svc = _build_service()
        token = svc.create_token(req)
        return _proxy_response(200, json.dumps(token))
    except HttpClientError as e:
        return _proxy_response(
            502,
            json.dumps({"message": "upstream_error", "status_code": e.status_code, "details": e.response_body}),
        )
    except Exception as e:
        print(f"Internal error in auth_token: {e}")
        return _proxy_response(500, json.dumps({"message": "internal_error"}))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Log para auditoria de paths do API Gateway
    print(f"EVENT_RECEIVED: {json.dumps(event)}")

    path = event.get("rawPath") or event.get("path") or ""
    
    # Extração robusta do método HTTP
    request_context = event.get("requestContext") or {}
    http_ctx = request_context.get("http")
    if isinstance(http_ctx, dict):
        method = http_ctx.get("method", "GET")
    else:
        method = event.get("httpMethod", "GET")

    # Resposta imediata para Preflight do Navegador
    if method == "OPTIONS":
        return _proxy_response(204, "")

    # Roteamento manual baseado no path completo enviado pelo Terraform
    if path == "/health" and method == "GET":
        return _handle_health()
    if path == "/integrations/melhorenvio/status" and method == "GET":
        return _handle_status()
    if path == "/integrations/melhorenvio/authorize-url" and method == "GET":
        return _handle_authorize_url(event)
    if path == "/integrations/melhorenvio/callback" and method == "GET":
        return _handle_callback(event)
    if path == "/auth/token" and method == "POST":
        return _handle_auth_token(event)

    # Fallback caso nenhuma rota coincida
    print(f"NOT_FOUND: {method} {path}")
    return _proxy_response(404, json.dumps({"message": "not_found", "path": path, "method": method}))