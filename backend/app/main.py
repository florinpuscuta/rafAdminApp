import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cleanup import cleanup_scheduler
from app.core.config import settings
from app.core.db import get_session
from app.core.logging import (
    bind_request_context,
    configure_logging,
    new_request_id,
)
from app.core.rate_limit import limiter
from app.core.registry import MODULE_ROUTERS

configure_logging()
_log = logging.getLogger("adeplast.http")

# Sentry — init doar dacă DSN e setat; fără el app-ul rulează normal.
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[FastApiIntegration(), AsyncPGIntegration()],
        # Ascunde headere sensibile din request-uri raportate
        send_default_pii=False,
    )

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """
    FastAPI lifespan — pornește scheduler-ul de cleanup ca task background și
    îl oprește curat la shutdown. În test env (APP_ENV=test) îl sărim — testele
    nu au nevoie de background work care poate polua starea.
    """
    task: asyncio.Task | None = None
    if settings.app_env != "test":
        task = asyncio.create_task(cleanup_scheduler(interval_hours=24))
        _log.info("cleanup scheduler started")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


app = FastAPI(
    title="Adeplast SaaS",
    description=(
        "Multi-tenant SaaS pentru analiza vânzărilor Key Accounts.\n\n"
        "**Autentificare**: Bearer JWT. Obține-l cu `POST /api/auth/login`, "
        "apasă butonul `Authorize` sus-dreapta și lipește `accessToken`.\n\n"
        "**Conturi programatice**: setează header `X-API-Key: <key>` în loc "
        "de Bearer (creează din UI: *Settings → API keys*)."
    ),
    version=os.environ.get("APP_VERSION", "dev"),
    contact={"name": "Adeplast SaaS"},
    # Swagger UI config — pre-populează scheme-ul Bearer vizual
    swagger_ui_parameters={
        "persistAuthorization": True,  # păstrează token-ul la refresh
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    },
    lifespan=_lifespan,
)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Propagă un request_id pe tot stack-ul + loghează fiecare request cu latență.
    Request-ID vine din header-ul `X-Request-ID` dacă e trimis (util pt
    corelare upstream/loadbalancer), altfel se generează.
    """

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or new_request_id()
        bind_request_context(request_id=req_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = int((time.perf_counter() - start) * 1000)
            _log.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "latency_ms": latency_ms,
                },
            )
            raise
        latency_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = req_id
        _log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Setează headere de securitate pe fiecare response. Nginx/proxy-ul poate
    le seta deja pentru HTML — ăsta e defense-in-depth și acoperă API-ul
    direct (util când e consumat fără proxy).

    Nu setăm Content-Security-Policy aici — e prea app-specific și ar trebui
    setat cu atenție în nginx pentru HTML (nu pt API JSON).
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Previne embedding în iframe-uri străine (clickjacking)
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Previne MIME sniffing — browserul respectă Content-Type-ul setat
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Nu trimite Referer la cross-origin — evită leak de URL-uri sensibile
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Dezactivează API-uri browser pe care nu le folosim (camera, geolocation etc)
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        # HSTS — doar în prod (dev pe http ar rămâne blocat dacă userul revine la http)
        if settings.app_env != "dev":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


app.add_middleware(AccessLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def _compute_retry_after(exc: RateLimitExceeded) -> int:
    """
    Extrage un retry-after în secunde din string-ul slowapi (ex: "15 per 1 minute").
    Nu e perfect (e lungimea ferestrei, nu timpul până la reset) dar e un upper-bound
    rezonabil pentru UX — clientul afișează „reîncearcă în ≤60s".
    """
    try:
        detail = str(exc.detail)
        # Format: "<limit> per <n> <unit>"
        parts = detail.split("per")
        if len(parts) != 2:
            return 60
        tail = parts[1].strip().split()
        n = int(tail[0]) if tail and tail[0].isdigit() else 1
        unit = tail[-1].rstrip("s") if len(tail) >= 2 else "minute"
        return n * _UNIT_SECONDS.get(unit, 60)
    except Exception:  # noqa: BLE001
        return 60


async def _rate_limit_handler(request, exc: RateLimitExceeded):
    retry_after = _compute_retry_after(exc)
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "code": "rate_limited",
                "message": f"Prea multe cereri — reîncearcă în ≤{retry_after}s.",
                "retryAfter": retry_after,
            }
        },
        headers={"Retry-After": str(retry_after)},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# CORS — origin-urile permise vin din env (CORS_ALLOWED_ORIGINS comma-separated).
# În dev default e localhost:5173. În prod trebuie setat domeniul real, altfel
# frontend-ul e blocat de browser cu "blocked by CORS policy".
_cors_origins = [
    o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_STARTED_AT = datetime.now(timezone.utc)


@app.get("/api/health")
async def health(session: AsyncSession = Depends(get_session)):
    """
    Health check extins — verifică fiecare component critic și raportează
    status per componentă. Returnează 200 dacă TOATE sunt ok, altfel 503.

    Util pentru uptime-monitoring (Uptime Kuma, Better Stack, etc.).
    """
    components: dict[str, dict[str, str]] = {}

    # DB
    db_start = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        components["db"] = {
            "status": "ok",
            "latency_ms": str(int((time.perf_counter() - db_start) * 1000)),
        }
    except Exception as exc:  # noqa: BLE001
        components["db"] = {"status": "fail", "error": str(exc)[:200]}

    # MinIO
    minio_start = time.perf_counter()
    try:
        from app.core.storage import internal_client
        internal_client().bucket_exists(settings.minio_bucket)
        components["storage"] = {
            "status": "ok",
            "latency_ms": str(int((time.perf_counter() - minio_start) * 1000)),
        }
    except Exception as exc:  # noqa: BLE001
        components["storage"] = {"status": "fail", "error": str(exc)[:200]}

    # SMTP — verificăm doar config prezent (fără să facem conexiune)
    if settings.smtp_host:
        components["email"] = {"status": "configured", "host": settings.smtp_host}
    else:
        components["email"] = {"status": "dev-log"}

    # Sentry
    components["sentry"] = {
        "status": "configured" if settings.sentry_dsn else "disabled",
    }

    all_ok = all(c["status"] in ("ok", "configured", "dev-log", "disabled") for c in components.values())
    body = {
        "status": "ok" if all_ok else "degraded",
        "env": settings.app_env,
        "components": components,
    }
    return JSONResponse(status_code=200 if all_ok else 503, content=body)


@app.get("/api/version")
async def version():
    """
    Informații build/runtime — utile post-deploy ca să confirmi că versiunea
    corectă rulează. `APP_VERSION` și `APP_GIT_SHA` vin din env (setate de
    CI/Docker build). Fallback la `unknown`.
    """
    return {
        "version": os.environ.get("APP_VERSION", "dev"),
        "gitSha": os.environ.get("APP_GIT_SHA", "unknown"),
        "buildTime": os.environ.get("APP_BUILD_TIME", "unknown"),
        "env": settings.app_env,
        "startedAt": _STARTED_AT.isoformat(),
        "uptimeSeconds": int((datetime.now(timezone.utc) - _STARTED_AT).total_seconds()),
    }


for router in MODULE_ROUTERS:
    app.include_router(router)
