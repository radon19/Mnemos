"""Broker configuration, loaded only from the environment (pydantic-settings)."""

from __future__ import annotations

import base64
import binascii
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .crypto import X25519_KEY_BYTES, assert_key_length


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    near_network: str = "testnet"
    near_rpc_url: str = "https://test.rpc.fastnear.com"
    mnemos_contract_id: str
    mnemos_owner_account: str
    mnemos_agent_account: str
    mnemos_broker_account: str

    broker_near_account: str
    broker_near_secret_key: SecretStr
    broker_x25519_private_key: SecretStr

    database_url: str
    session_secret: SecretStr
    session_ttl_minutes: int = Field(default=30, ge=1, le=1440)
    session_cookie_secure: bool = False
    broker_public_url: str = "http://localhost:8000"
    broker_recipient: str = "localhost:8000"
    allowed_origins: str = "http://localhost:3000"

    nearai_api_key: SecretStr
    nearai_model: str = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
    nearai_base_url: str = "https://cloud-api.near.ai/v1"

    auth_rate_limit_per_minute: int = Field(default=20, ge=1, le=600)
    ask_rate_limit_per_minute: int = Field(default=10, ge=1, le=600)
    max_request_bytes: int = Field(default=32768, ge=1024, le=1_048_576)
    max_question_chars: int = Field(default=2000, ge=1, le=8000)
    sweeper_interval_seconds: int = Field(default=60, ge=10, le=3600)
    sweeper_enabled: bool = True
    retention_enabled: bool = True
    retention_interval_seconds: int = Field(default=3600, ge=60, le=86_400)
    max_vault_items: int = Field(default=500, ge=1, le=10_000)
    redteam_rate_limit_per_minute: int = Field(default=3, ge=1, le=60)
    log_level: str = "INFO"

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, value: str) -> str:
        origins = [part.strip() for part in value.split(",") if part.strip()]
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one origin")
        return ",".join(origins)

    @property
    def allowed_origin_list(self) -> list[str]:
        return [part for part in self.allowed_origins.split(",") if part]

    @property
    def broker_private_key(self) -> bytes:
        raw = self.broker_x25519_private_key.get_secret_value()
        try:
            key = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("BROKER_X25519_PRIVATE_KEY must be valid base64") from error
        assert_key_length("broker private key", key, X25519_KEY_BYTES)
        return key

    @property
    def session_secret_bytes(self) -> bytes:
        value = self.session_secret.get_secret_value().encode()
        if len(value) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 bytes")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
