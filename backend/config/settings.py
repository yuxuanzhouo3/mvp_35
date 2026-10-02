from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    auth_mode: str = "demo"
    storage_engine: str = "json"
    cloudbase_env_id: str = ""
    cloudbase_region: str = "ap-shanghai"
    data_path: str = "data/store.json"
    hunyuan_enabled: bool = False
    tongyi_enabled: bool = False
    hunyuan_api_key: str = ""
    ses_mode: str = "mock"
    wechat_pay_mode: str = "disabled"
    ledger_hmac_secret: str = "demo-ledger-secret"
    demo_signing_helper: bool = True
    worker_token: str = "demo-worker"
    quality_threshold: int = 60
    rules_version: str = "pg-rules-1.0"
    prompt_version: str = "prompt-v1"
    session_secret: str = "demo-session-secret"
    access_ttl_seconds: int = 3600
    refresh_ttl_seconds: int = 1_209_600
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
