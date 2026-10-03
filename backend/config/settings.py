from pathlib import Path

from pydantic import AliasChoices, Field
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
    wechat_pay_appid: str = ""
    wechat_pay_mchid: str = ""
    wechat_pay_serial_no: str = ""
    wechat_pay_private_key: str = ""
    wechat_pay_api_v3_key: str = ""
    wechat_pay_platform_public_key: str = ""
    wechat_pay_notify_url: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_miniprogram_app_id: str = ""
    wechat_miniprogram_app_secret: str = ""
    wechat_oauth_state_secret: str = ""
    wechat_oauth_redirect: str = "https://pickglobal.mornscience.top/login/wechat"
    auth_email_smtp_host: str = ""
    auth_email_smtp_port: int = 465
    auth_email_smtp_user: str = ""
    auth_email_smtp_pass: str = ""
    auth_email_from: str = ""
    public_web_origin: str = "https://pickglobal.mornscience.top"
    sms_secret_id: str = Field(default="", validation_alias=AliasChoices("TENCENT_SMS_SECRET_ID", "SMS_SECRET_ID"))
    sms_secret_key: str = Field(default="", validation_alias=AliasChoices("TENCENT_SMS_SECRET_KEY", "SMS_SECRET_KEY"))
    sms_sdk_app_id: str = Field(default="", validation_alias=AliasChoices("TENCENT_SMS_APP_ID", "SMS_SDK_APP_ID"))
    sms_sign_name: str = Field(default="", validation_alias=AliasChoices("TENCENT_SMS_SIGN_NAME", "SMS_SIGN_NAME"))
    sms_template_id: str = Field(default="", validation_alias=AliasChoices("TENCENT_SMS_TEMPLATE_ID", "SMS_TEMPLATE_ID"))
    sms_region: str = "ap-guangzhou"
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_alipay_public_key: str = ""
    alipay_gateway_url: str = "https://openapi.alipay.com/gateway.do"
    alipay_notify_url: str = ""
    alipay_aes_key: str = ""
    payment_test_amount_fen: int = 0
    ledger_hmac_secret: str = "demo-ledger-secret"
    demo_signing_helper: bool = True
    worker_token: str = "demo-worker"
    quality_threshold: int = 60
    rules_version: str = "pg-rules-1.0"
    fx_api_url: str = "https://api.frankfurter.dev/v1/latest"
    pricer_api_url: str = ""
    pricer_api_key: str = ""
    prompt_version: str = "prompt-v1"
    session_secret: str = "demo-session-secret"
    access_ttl_seconds: int = 3600
    refresh_ttl_seconds: int = 1_209_600
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
