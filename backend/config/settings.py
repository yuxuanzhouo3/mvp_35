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
    alibaba_app_key: str = ""
    alibaba_app_secret: str = ""
    alibaba_access_token: str = ""
    alibaba_refresh_token: str = ""
    alibaba_refresh_token_timeout: str = ""
    taobao_app_key: str = ""
    taobao_app_secret: str = ""
    taobao_adzone_id: str = ""
    pdd_client_id: str = ""
    pdd_client_secret: str = ""
    pdd_pid: str = ""
    jd_app_key: str = ""
    jd_app_secret: str = ""
    amazon_access_key: str = ""
    amazon_secret_key: str = ""
    amazon_partner_tag: str = ""
    walmart_publisher_id: str = ""
    walmart_consumer_id: str = ""
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    reply_interval_hours: int = 24
    amazon_sp_client_id: str = ""
    amazon_sp_client_secret: str = ""
    amazon_sp_refresh_token: str = ""
    walmart_market_client_id: str = ""
    walmart_market_client_secret: str = ""
    taobao_session: str = ""
    pdd_access_token: str = ""
    temu_app_key: str = ""
    temu_app_secret: str = ""
    temu_access_token: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_access_token: str = ""
    linkedin_ad_account_id: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_page_id: str = ""
    facebook_page_access_token: str = ""
    wecom_corp_id: str = ""
    wecom_contact_secret: str = ""
    wecom_follow_userid: str = ""
    douyin_client_key: str = ""
    douyin_client_secret: str = ""
    douyin_access_token: str = ""
    xhs_app_id: str = ""
    xhs_app_secret: str = ""
    xhs_access_token: str = ""
    kuaishou_app_id: str = ""
    kuaishou_app_secret: str = ""
    kuaishou_access_token: str = ""
    alibaba_intl_app_key: str = ""
    alibaba_intl_app_secret: str = ""
    alibaba_intl_access_token: str = ""
    qichacha_app_key: str = ""
    qichacha_secret_key: str = ""
    tianyancha_token: str = ""
    qixin_app_key: str = ""
    qixin_secret_key: str = ""
    agency_parent_account_id: str = ""
    prompt_version: str = "prompt-v1"
    session_secret: str = "demo-session-secret"
    access_ttl_seconds: int = 3600
    refresh_ttl_seconds: int = 1_209_600
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
