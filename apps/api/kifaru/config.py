"""Application settings. Every value can be overridden by environment variables (prefix KIFARU_).

Secrets are never committed: in production they are injected from AWS Secrets Manager into the ECS task
environment; locally they come from `.env` (git-ignored) — see `.env.example`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KIFARU_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    app_name: str = "KIFARU PORTOS API"
    api_version: str = "0.1.0"
    log_level: str = "INFO"

    # Database — PostgreSQL in all deployed environments; SQLite permitted for `test` and quick local runs.
    database_url: str = "sqlite:///./kifaru_dev.db"
    db_echo: bool = False
    # Hosted PostgreSQL (e.g. Supabase): force TLS and/or transaction-pooler-safe settings even if the host name does not reveal it
    db_require_ssl: bool = False
    db_pooler_transaction_mode: bool = False

    # Redis (optional locally; required in staging/prod for multi-instance WebSocket fan-out)
    redis_url: str | None = None

    # MQTT broker used by the ingest service (EMQX locally, AWS IoT Core in the cloud)
    mqtt_host: str | None = None
    mqtt_port: int = 8883
    mqtt_client_id: str = "kifaru-ingest"
    mqtt_tls_ca: str | None = None
    mqtt_tls_cert: str | None = None
    mqtt_tls_key: str | None = None

    # Auth
    jwt_secret: str = Field(default="CHANGE-ME-dev-only-secret-not-for-production", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    mfa_required_roles: list[str] = ["platform_admin", "weighbridge_operator", "port_controller", "auditor"]
    mfa_issuer: str = "KIFARU PORTOS"

    # Signing key (Ed25519, base64 seed). Generated on first start in dev; MUST be provided in staging/prod.
    signing_seed_b64: str | None = None
    signing_key_id: str = "platform-dev-key"

    # Object storage (S3 in cloud; local folder in dev)
    s3_bucket: str | None = None
    s3_region: str = "af-south-1"
    local_object_dir: str = "./objects"

    # Clearance engine configuration
    limits_version: str = "KE-EAC-VLC-REG-2018-schedule-v2"
    audit_sample_rate: float = 0.02  # 2 % of GREEN-eligible passes diverted for random audit
    identity_min_confidence: float = 0.90
    coverage_factor_k: float = 2.0

    # PII column encryption key (base64, 32 bytes). Required in staging/prod; derived from the JWT secret in dev/test.
    pii_key_b64: str | None = None
    # Privileged roles must have enrolled MFA before any privileged action (None = enforce in staging/prod only)
    mfa_enforce_enrolment: bool | None = None
    # Pilot recommendation: require two independent identity sources (RFID and ANPR) for GREEN
    identity_require_two_sources: bool = False
    # RCS v2: Load Compliance Token policy (validity windows in hours by token source; consistency tolerance by source)
    token_validity_hours_port: int = 36
    token_validity_hours_origin: int = 36
    token_validity_hours_lane: int = 24
    token_validity_hours_road: int = 24
    token_tolerance_port: float = 0.08
    token_tolerance_origin: float = 0.08
    token_tolerance_lane: float = 0.08
    token_tolerance_road: float = 0.11
    # Audit rates by trust tier (1 port, 2 approved origin scale, 3 road node/lane, 4 on-board record only)
    audit_rate_tier1: float = 0.02
    audit_rate_tier2: float = 0.04
    audit_rate_tier3: float = 0.03
    audit_rate_tier4: float = 1.0
    # Reg 14: a second overload in the same journey triples the fee; journey window used to detect it (hours)
    release_order_journey_hours: int = 72
    # Which ingest transport the `kifaru.ingest` entrypoint runs: iot_core (SQS from IoT rule) | emqx (MQTT) | none
    iot_mode: str = "emqx"
    events_queue_url: str | None = None

    # Public URL used in QR codes
    public_base_url: str = "http://localhost:5173"

    # Rate limiting
    rate_limit_per_minute: int = 300
    # Authenticated-user cache (seconds). Every request otherwise costs three database round trips (user, roles, PII)
    # before its own work; against a remote database (Supabase) that is over a second. Entries are invalidated on
    # role / activation / MFA changes; 0 disables the cache.
    auth_cache_seconds: int = 60

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_deployed(self) -> bool:
        return self.env in ("staging", "prod")

    def validate_for_deployment(self) -> None:
        """Refuse to start a deployed environment with development defaults."""
        if not self.is_deployed:
            return
        problems = []
        if self.jwt_secret.startswith("CHANGE-ME"):
            problems.append("KIFARU_JWT_SECRET is the development default")
        if not self.signing_seed_b64:
            problems.append("KIFARU_SIGNING_SEED_B64 is not set")
        if not self.pii_key_b64:
            problems.append("KIFARU_PII_KEY_B64 is not set")
        if self.is_sqlite:
            problems.append("SQLite is not permitted in deployed environments")
        if problems:
            raise RuntimeError("Unsafe deployment configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
