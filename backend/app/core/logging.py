"""
Structured JSON logging setup.

În dev (`APP_ENV=dev`): logging lizibil pe linii (format colorat).
În prod: fiecare linie e un JSON cu `timestamp`, `level`, `logger`, `message` +
câmpuri extra (`request_id`, `user_id`, `tenant_id`, `path`, `method`, `status`,
`latency_ms`, `exception`).

Logger-ele stdlib (uvicorn, sqlalchemy, etc) sunt unificate în acest format ca
pipeline-ul de loguri (Sentry / Loki / stdout-to-file) să aibă un singur schema.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

# Context propagat pe toată durata unui request
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
_tenant_id_ctx: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def bind_request_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> None:
    if request_id is not None:
        _request_id_ctx.set(request_id)
    if user_id is not None:
        _user_id_ctx.set(user_id)
    if tenant_id is not None:
        _tenant_id_ctx.set(tenant_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


class _JSONFormatter(logging.Formatter):
    """Formatter care emite o linie JSON per record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)
            )
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        rid = _request_id_ctx.get()
        if rid:
            payload["request_id"] = rid
        uid = _user_id_ctx.get()
        if uid:
            payload["user_id"] = uid
        tid = _tenant_id_ctx.get()
        if tid:
            payload["tenant_id"] = tid

        # Câmpuri extra trimise prin logger.info("msg", extra={"foo": ...})
        standard = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName",
        }
        for k, v in record.__dict__.items():
            if k not in standard and not k.startswith("_"):
                try:
                    json.dumps(v)  # serializable?
                    payload[k] = v
                except TypeError:
                    payload[k] = str(v)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class _DevFormatter(logging.Formatter):
    """Formatter compact pentru dev (o linie per log, lizibil)."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{time.strftime('%H:%M:%S', time.localtime(record.created))}."
            f"{int(record.msecs):03d} "
            f"{record.levelname:<5} {record.name}: {record.getMessage()}"
        )
        rid = _request_id_ctx.get()
        if rid:
            base = f"[{rid[:8]}] {base}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging() -> None:
    """Se apelează o singură dată la pornirea aplicației."""
    is_prod = settings.app_env != "dev"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter() if is_prod else _DevFormatter())

    root = logging.getLogger()
    # Evită dublarea handler-elor la hot-reload
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Uvicorn + sqlalchemy au propriile handler-uri — le dezactivăm ca să
    # folosească doar root-ul nostru (evită linii duplicate, unul per handler).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

    # SQL queries → doar WARNING (evită spam: fiecare request generează zeci de linii BEGIN/SELECT/ROLLBACK)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # Suprimă access log redundant — noi logăm în AccessLogMiddleware cu mai mult context
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def new_request_id() -> str:
    """UUID4 fără dash-uri, pe 24 caractere."""
    return uuid.uuid4().hex[:24]
