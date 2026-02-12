from __future__ import annotations

from functools import lru_cache
import json
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayHttpResolver

from controller import BadRequestError, build_authorize_url, insert_cart, refresh_token, request_token
from repository import MelhorEnvioApiError, MelhorEnvioRepository
from service import ConfigurationError, MelhorEnvioService
from settings import get_settings

logger = Logger()
tracer = Tracer()
app = APIGatewayHttpResolver()


@lru_cache(maxsize=1)
def _get_service() -> MelhorEnvioService:
    settings = get_settings()
    repo = MelhorEnvioRepository(
        base_url=settings.melhor_envio_base_url,
        timeout_seconds=settings.http_timeout_seconds,
        user_agent=settings.user_agent,
    )
    return MelhorEnvioService(settings=settings, repository=repo)


def _json(status_code: int, body: dict[str, Any]) -> Response:
    return Response(status_code=status_code, content_type="application/json", body=json.dumps(body))


def _extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


@app.get("/health")
def health() -> Response:
    return _json(200, {"status": "ok"})


@app.post("/auth/authorize-url")
def authorize_url() -> Response:
    service = _get_service()
    body = app.current_event.json_body or {}
    payload = build_authorize_url(service=service, body=body)
    return _json(200, payload)


@app.post("/auth/token")
def auth_token() -> Response:
    service = _get_service()
    body = app.current_event.json_body or {}
    payload = request_token(service=service, body=body)
    return _json(200, payload)


@app.post("/auth/refresh")
def auth_refresh() -> Response:
    service = _get_service()
    body = app.current_event.json_body or {}
    payload = refresh_token(service=service, body=body)
    return _json(200, payload)


@app.post("/me/cart")
def me_cart() -> Response:
    access_token = _extract_bearer_token(app.current_event.headers.get("authorization"))
    if not access_token:
        return _json(401, {"message": "Missing or invalid Authorization header (expected: Bearer <token>)"})

    service = _get_service()
    body = app.current_event.json_body or {}
    payload = insert_cart(service=service, access_token=access_token, body=body)
    return _json(200, payload)


@app.exception_handler(BadRequestError)
def handle_bad_request(exc: BadRequestError) -> Response:
    logger.info("bad_request", extra={"error": str(exc)})
    return _json(400, {"message": str(exc)})


@app.exception_handler(ConfigurationError)
def handle_config_error(exc: ConfigurationError) -> Response:
    logger.error("configuration_error", extra={"error": str(exc)})
    return _json(500, {"message": "Configuration error"})


@app.exception_handler(MelhorEnvioApiError)
def handle_me_api_error(exc: MelhorEnvioApiError) -> Response:
    logger.warning(
        "melhor_envio_api_error",
        extra={"status_code": exc.status_code, "payload": exc.payload},
    )
    body = exc.payload if isinstance(exc.payload, dict) else {"message": str(exc)}
    return _json(exc.status_code, body)


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)

