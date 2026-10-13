-- Twin of rollback.migrate.up_0001. Live MVP data stays in the CloudBase JSON store.
-- Apply this only on PostgreSQL after a logical load. Down copies rows back before drop.

CREATE TABLE IF NOT EXISTS schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  email text,
  quality_score numeric,
  score_v2 numeric,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_v2 numeric;
UPDATE leads SET score_v2 = quality_score WHERE score_v2 IS NULL AND quality_score IS NOT NULL;

CREATE TABLE IF NOT EXISTS analysis_reports (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS selection_reports (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
INSERT INTO selection_reports (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM analysis_reports
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS outreach_messages (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS deliveries (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
INSERT INTO deliveries (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM outreach_messages
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS payment_orders (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  idempotency_key text,
  amount_fen bigint,
  status text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS payments (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  idempotency_key text,
  amount_fen bigint,
  status text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
INSERT INTO payments (id, tenant_id, idempotency_key, amount_fen, status, payload)
SELECT id, tenant_id, idempotency_key, amount_fen, status, payload FROM payment_orders
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS metric_snapshots (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS kpi_metrics (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
INSERT INTO kpi_metrics (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM metric_snapshots
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS activation_jobs (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS recall_jobs (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS recalls (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  trigger text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
INSERT INTO recalls (id, tenant_id, trigger, payload)
SELECT id, tenant_id, 'cold_start', payload FROM activation_jobs
ON CONFLICT (id) DO NOTHING;
INSERT INTO recalls (id, tenant_id, trigger, payload)
SELECT id, tenant_id, 'churn', payload FROM recall_jobs
ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_migrations (version) VALUES ('0001_postgres_shape')
ON CONFLICT (version) DO NOTHING;
