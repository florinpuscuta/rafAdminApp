from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_ctx.verify(password, password_hash)


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    *,
    expire_minutes: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    ttl = expire_minutes if expire_minutes is not None else settings.jwt_expire_minutes
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc


# ── Password complexity ─────────────────────────────────────────────────────

_COMMON_WEAK_PREFIXES = (
    "password", "parola", "12345", "qwerty", "admin",
    "welcome", "letmein", "abc123",
)


def validate_password_strength(password: str) -> str | None:
    """
    Validare minimă complexitate server-side. Returnează None dacă e OK,
    altfel un string uman cu motivul respingerii (safe to show to user).

    Reguli (intenționat moderate, nu draconice):
      - minim 8 caractere
      - cel puțin 2 clase de caractere (dintre: lower, upper, digit, symbol)
      - nu începe cu un pattern comun slab ("password", "parola", "12345", etc)
      - nu e 8+ repetări ale aceluiași caracter (ex "aaaaaaaa")

    Parolele pur numerice / pur litere de aceeași clasă sunt respinse chiar
    dacă sunt lungi — client-side indicator-ul pe frontend aplică aceleași
    reguli ca să fie consistent.
    """
    if len(password) < 8:
        return "Parola trebuie să aibă minim 8 caractere."

    # Pattern trivial: un singur caracter repetat
    if len(set(password)) == 1:
        return "Parola e prea simplă (caractere repetate)."

    lower = any(c.islower() for c in password)
    upper = any(c.isupper() for c in password)
    digit = any(c.isdigit() for c in password)
    symbol = any(not c.isalnum() for c in password)
    classes = sum((lower, upper, digit, symbol))
    if classes < 2:
        return (
            "Parola trebuie să conțină cel puțin 2 tipuri de caractere "
            "(litere mici, litere mari, cifre, sau simboluri)."
        )

    # Reject only "password123"-style combos — prefix slab + suffix trivial
    # (cifre, simboluri simple). Ex: "parola1234" respins, dar "ParolaRealistă_77" OK
    # (are litere în suffix → nu e un pattern previzibil automat).
    lowered = password.lower()
    for weak in _COMMON_WEAK_PREFIXES:
        if lowered.startswith(weak):
            suffix = lowered[len(weak):]
            # Pattern trivial: doar cifre/simboluri simple după prefix-ul slab
            if suffix == "" or all(c.isdigit() or c in "!@#$_-." for c in suffix):
                return "Parola e prea previzibilă (începe cu un pattern comun)."

    return None
