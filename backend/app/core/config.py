from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas"
    app_env: str = "dev"

    jwt_secret: str = "dev-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15  # access token = short-lived (redus de la 60)
    refresh_token_expire_days: int = 30

    password_reset_expire_minutes: int = 30
    email_verify_expire_hours: int = 48
    frontend_url: str = "http://localhost:5173"

    # CORS allowed origins — listă comma-separated din env. Default permite dev.
    # În prod setează ex: CORS_ALLOWED_ORIGINS=https://app.exemplu.ro,https://staging.exemplu.ro
    cors_allowed_origins: str = "http://localhost:5173"

    failed_login_max_attempts: int = 5
    failed_login_lock_minutes: int = 15

    # MinIO / S3 pentru Gallery
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "adeplast-saas"
    minio_secure: bool = False
    # Endpoint vizibil din browser (pentru presigned URLs) — diferă de cel intern.
    minio_public_endpoint: str = "localhost:9000"

    # Sentry — opțional; lipsește → error tracking dezactivat
    sentry_dsn: str | None = None
    sentry_environment: str = "dev"
    sentry_traces_sample_rate: float = 0.1

    # SMTP — dacă smtp_host nu e setat, emailurile se loghează (dev).
    # Exemple: Gmail (smtp.gmail.com:587 STARTTLS), Resend (smtp.resend.com:465 TLS),
    # Mailgun (smtp.mailgun.org:587 STARTTLS), SendGrid (smtp.sendgrid.net:587).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@adeplast-saas.local"
    smtp_from_name: str = "Adeplast SaaS"
    smtp_use_tls: bool = False       # True → conexiune TLS directă (port 465)
    smtp_use_starttls: bool = True   # True → STARTTLS după HELO (port 587)

    # AI Assistant — provider auto-detectat după primul env var setat (ordinea de mai jos),
    # sau forțat prin AI_PROVIDER. Dacă niciunul nu e setat → stub diagnostic.
    ai_provider: str | None = None  # "anthropic" | "openai" | "xai" | "deepseek"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    xai_api_key: str | None = None
    xai_model: str = "grok-2-latest"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"


settings = Settings()
