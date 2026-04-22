"""Teste pentru CORS — verifică că Origin-urile permise vin din config."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_cors_preflight_allows_configured_origin(client: AsyncClient):
    """Preflight OPTIONS pentru origin-ul din config primește Access-Control-* headers."""
    resp = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS preflight → 200/204 cu headers Access-Control-*
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_actual_request_gets_cors_header_for_allowed_origin(client: AsyncClient):
    """GET cu Origin permis → response include access-control-allow-origin."""
    resp = await client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code in (200, 503)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_disallowed_origin_gets_no_cors_header(client: AsyncClient):
    """Origin nepermis → browser-ul va bloca (no Access-Control-Allow-Origin)."""
    resp = await client.get(
        "/api/health",
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code in (200, 503)
    # FastAPI's CORSMiddleware nu scrie header-ul pentru origin-uri nepermise
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"
