"""Teste pentru formatul răspunsului 429 (retry-after)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.main import _compute_retry_after


class _MockExc:
    def __init__(self, detail: str):
        self.detail = detail


def test_compute_retry_after_minute():
    assert _compute_retry_after(_MockExc("15 per 1 minute")) == 60


def test_compute_retry_after_multiple_minutes():
    assert _compute_retry_after(_MockExc("100 per 5 minutes")) == 300


def test_compute_retry_after_hour():
    assert _compute_retry_after(_MockExc("1000 per 1 hour")) == 3600


def test_compute_retry_after_second():
    assert _compute_retry_after(_MockExc("1 per 30 seconds")) == 30


def test_compute_retry_after_fallback_on_garbage():
    assert _compute_retry_after(_MockExc("garbage")) == 60


@pytest.mark.asyncio
async def test_429_response_includes_retry_after_header_and_body(client: AsyncClient):
    """Trigger rate limit pe /login (15/min) cu același IP."""
    ip = "198.51.100.50"
    # Epuizăm limita
    last_resp = None
    for _ in range(20):
        last_resp = await client.post(
            "/api/auth/login",
            headers={"X-Forwarded-For": ip},
            json={"email": "nobody@example.com", "password": "x"},
        )
        if last_resp.status_code == 429:
            break

    assert last_resp is not None
    assert last_resp.status_code == 429
    assert last_resp.headers.get("retry-after") is not None
    body = last_resp.json()
    assert body["detail"]["code"] == "rate_limited"
    assert isinstance(body["detail"]["retryAfter"], int)
    assert body["detail"]["retryAfter"] > 0
