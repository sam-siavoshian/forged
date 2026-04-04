"""Tests for CloudBrowserManager."""

from __future__ import annotations

import pytest
import httpx

from unittest.mock import AsyncMock, patch

from src.browser.cloud import CloudBrowserManager
from src.models import CloudBrowserSession


@pytest.fixture
def manager():
    return CloudBrowserManager(api_key="bu_test_key")


# --- create() ---


@pytest.mark.asyncio
async def test_create_success(manager: CloudBrowserManager):
    mock_response = httpx.Response(
        201,
        json={
            "id": "browser_abc123",
            "cdpUrl": "wss://cdp.browser-use.com/browser/abc123?token=xyz",
            "liveUrl": "https://live.browser-use.com/browser/abc123?token=xyz",
            "status": "running",
        },
        request=httpx.Request("POST", "https://api.browser-use.com/api/v3/browsers"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        session = await manager.create()

    assert isinstance(session, CloudBrowserSession)
    assert session.browser_id == "browser_abc123"
    assert session.cdp_url == "wss://cdp.browser-use.com/browser/abc123?token=xyz"
    assert session.live_url == "https://live.browser-use.com/browser/abc123?token=xyz"
    assert session.status == "running"

    # Verify correct API call
    call_kwargs = mock_client.post.call_args
    assert "browsers" in call_kwargs.args[0]
    assert call_kwargs.kwargs["headers"]["X-Browser-Use-API-Key"] == "bu_test_key"
    assert call_kwargs.kwargs["json"]["timeout"] == 120


@pytest.mark.asyncio
async def test_create_custom_params(manager: CloudBrowserManager):
    mock_response = httpx.Response(
        201,
        json={
            "id": "browser_xyz",
            "cdpUrl": "wss://example.com",
            "status": "running",
        },
        request=httpx.Request("POST", "https://api.browser-use.com/api/v3/browsers"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        session = await manager.create(
            timeout_minutes=60,
            proxy_country="GB",
            width=1280,
            height=720,
            enable_recording=False,
        )

    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs["json"]
    assert body["timeout"] == 60
    assert body["proxyCountryCode"] == "GB"
    assert body["browserScreenWidth"] == 1280
    assert body["browserScreenHeight"] == 720
    assert body["enableRecording"] is False


@pytest.mark.asyncio
async def test_create_missing_cdp_url_raises(manager: CloudBrowserManager):
    mock_response = httpx.Response(
        201,
        json={"id": "browser_abc", "status": "running"},
        request=httpx.Request("POST", "https://api.browser-use.com/api/v3/browsers"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="missing cdpUrl"):
            await manager.create()


@pytest.mark.asyncio
async def test_create_api_error(manager: CloudBrowserManager):
    mock_response = httpx.Response(
        500,
        json={"error": "internal"},
        request=httpx.Request("POST", "https://api.browser-use.com/api/v3/browsers"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await manager.create()


@pytest.mark.asyncio
async def test_create_timeout(manager: CloudBrowserManager):
    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.TimeoutException):
            await manager.create()


# --- stop() ---


@pytest.mark.asyncio
async def test_stop_success(manager: CloudBrowserManager):
    mock_response = httpx.Response(
        200,
        request=httpx.Request("DELETE", "https://api.browser-use.com/api/v3/browsers/browser_abc"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await manager.stop("browser_abc")  # Should not raise

    mock_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_stop_already_stopped_404(manager: CloudBrowserManager):
    """404 means browser already stopped — should not raise."""
    mock_response = httpx.Response(
        404,
        request=httpx.Request("DELETE", "https://api.browser-use.com/api/v3/browsers/browser_abc"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await manager.stop("browser_abc")  # Should not raise


@pytest.mark.asyncio
async def test_stop_server_error_raises(manager: CloudBrowserManager):
    mock_response = httpx.Response(
        500,
        json={"error": "internal"},
        request=httpx.Request("DELETE", "https://api.browser-use.com/api/v3/browsers/browser_abc"),
    )

    with patch("src.browser.cloud.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await manager.stop("browser_abc")


# --- API key handling ---


def test_missing_api_key_raises():
    """CloudBrowserManager should raise if no API key available."""
    import os

    env_backup = os.environ.pop("BROWSER_USE_API_KEY", None)
    try:
        with pytest.raises(RuntimeError, match="BROWSER_USE_API_KEY"):
            CloudBrowserManager()
    finally:
        if env_backup:
            os.environ["BROWSER_USE_API_KEY"] = env_backup
