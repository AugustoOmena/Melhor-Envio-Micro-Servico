from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from repository import MelhorEnvioRepository
from service import ConfigurationError, MelhorEnvioService
from settings import Settings


def _settings(**overrides) -> Settings:
    base: Settings = Settings(
        melhor_envio_base_url="https://sandbox.melhorenvio.com.br",
        melhor_envio_client_id="client-id",
        melhor_envio_client_secret="client-secret",
        melhor_envio_default_scope="shipment.read shipment.write",
        http_timeout_seconds=10.0,
        user_agent="ua",
    )
    return replace(base, **overrides)


def test_build_authorize_url_includes_required_params() -> None:
    repo = Mock(spec=MelhorEnvioRepository)
    svc = MelhorEnvioService(settings=_settings(), repository=repo)

    url = svc.build_authorize_url(redirect_uri="https://example.com/cb", scope=None, state="abc123")

    assert url.startswith("https://sandbox.melhorenvio.com.br/oauth/authorize?")
    assert "client_id=client-id" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcb" in url
    assert "response_type=code" in url
    assert "state=abc123" in url


def test_build_authorize_url_raises_when_missing_client_id() -> None:
    repo = Mock(spec=MelhorEnvioRepository)
    svc = MelhorEnvioService(settings=_settings(melhor_envio_client_id=None), repository=repo)

    with pytest.raises(ConfigurationError):
        svc.build_authorize_url(redirect_uri="https://example.com/cb", scope=None, state=None)


def test_exchange_token_calls_repository_with_client_credentials() -> None:
    repo = Mock(spec=MelhorEnvioRepository)
    repo.exchange_token.return_value = {"access_token": "x"}
    svc = MelhorEnvioService(settings=_settings(), repository=repo)

    payload = svc.exchange_token(
        grant_type="authorization_code",
        redirect_uri="https://example.com/cb",
        code="code123",
    )

    assert payload == {"access_token": "x"}
    repo.exchange_token.assert_called_once()
    sent = repo.exchange_token.call_args.kwargs["data"]
    assert sent["grant_type"] == "authorization_code"
    assert sent["client_id"] == "client-id"
    assert sent["client_secret"] == "client-secret"
    assert sent["redirect_uri"] == "https://example.com/cb"
    assert sent["code"] == "code123"


def test_refresh_token_calls_repository() -> None:
    repo = Mock(spec=MelhorEnvioRepository)
    repo.exchange_token.return_value = {"access_token": "new"}
    svc = MelhorEnvioService(settings=_settings(), repository=repo)

    payload = svc.refresh_token(refresh_token="rt")

    assert payload["access_token"] == "new"
    sent = repo.exchange_token.call_args.kwargs["data"]
    assert sent["grant_type"] == "refresh_token"
    assert sent["refresh_token"] == "rt"

