"""CloudBase document baseline. PostgreSQL names exist only after migrate up."""

ENGINE_CLOUDBASE = "cloudbase_documents"
ENGINE_POSTGRES = "postgresql"
BASELINE_VERSION = "baseline-cloudbase"
BASELINE_TAG = "baseline-cloudbase"

# Live collections written by backend/db/store.py. Rollback must restore these names.
CLOUDBASE_COLLECTIONS = (
    "users",
    "tenants",
    "tenant_members",
    "entitlements",
    "quota_balances",
    "products",
    "product_sources",
    "analysis_reports",
    "leads",
    "campaigns",
    "outreach_messages",
    "activation_jobs",
    "recall_jobs",
    "jobs",
    "payment_orders",
    "subscriptions",
    "usage_ledger",
    "commission_ledger",
    "raas_ledger",
    "metric_snapshots",
    "webhook_events",
    "suppressions",
    "ai_conversations",
    "ai_messages",
)

# Names introduced by the PostgreSQL 4S cutover. Absent after a full down.
POSTGRES_ONLY = (
    "selection_reports",
    "deliveries",
    "payments",
    "kpi_metrics",
    "recalls",
)

RENAMES = (
    ("analysis_reports", "selection_reports"),
    ("outreach_messages", "deliveries"),
    ("payment_orders", "payments"),
    ("metric_snapshots", "kpi_metrics"),
)

LEDGER_CLOUDBASE = ("payment_orders", "commission_ledger", "raas_ledger")
LEDGER_POSTGRES = ("payments", "commission_ledger", "raas_ledger")
LEDGER_STATUSES = frozenset({"succeeded", "posted"})

FLAGS = (
    "auth.sso",
    "auth.mfa",
    "payment.raas",
    "selection.auto_deal",
    "acquisition.social",
    "acquisition.ecommerce",
    "acquisition.expo",
    "acquisition.agency",
    "ai.agent",
    "ai.finetune",
    "digital_human",
    "geo_seo",
    "raas",
    "global_multi_active",
)

MIGRATION_ORDER = ("0001_postgres_shape", "0002_contract_score")
