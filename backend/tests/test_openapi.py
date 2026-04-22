"""Teste pentru /openapi.json — securitate + metadata."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_openapi_json_served(client: AsyncClient):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Adeplast SaaS"
    assert "Bearer JWT" in schema["info"]["description"]


async def test_openapi_has_bearer_security_scheme(client: AsyncClient):
    """FastAPI generează automat schema BearerAuth pt HTTPBearer dependency."""
    resp = await client.get("/openapi.json")
    schema = resp.json()
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    # Poate fi "HTTPBearer" sau alt nume — verificăm că există măcar un scheme bearer
    bearer = next(
        (v for v in security_schemes.values() if v.get("type") == "http" and v.get("scheme") == "bearer"),
        None,
    )
    assert bearer is not None, f"Nu există Bearer scheme în {list(security_schemes.keys())}"


async def test_authenticated_endpoints_declare_security(client: AsyncClient):
    """Endpoint-urile cu Depends(get_current_user) trebuie să apară ca necesitând auth."""
    resp = await client.get("/openapi.json")
    schema = resp.json()
    # /api/stores GET e autentificat
    stores_get = schema["paths"]["/api/stores"]["get"]
    assert "security" in stores_get and len(stores_get["security"]) > 0


async def test_public_endpoints_do_not_require_security(client: AsyncClient):
    """/api/health și /api/version sunt publice — nu trebuie să aibă security."""
    resp = await client.get("/openapi.json")
    schema = resp.json()
    for public_path in ["/api/health", "/api/version"]:
        path_get = schema["paths"][public_path]["get"]
        # "security" poate lipsi sau să fie listă goală
        assert not path_get.get("security"), f"{public_path} nu ar trebui să ceară auth"


async def test_swagger_ui_served(client: AsyncClient):
    resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text.lower()
