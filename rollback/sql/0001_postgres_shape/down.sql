-- Reverse 0001. Copy PostgreSQL tables back onto CloudBase names, then drop the new tables.
-- score_v2 is an expand column; quality_score stays.

INSERT INTO analysis_reports (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM selection_reports
ON CONFLICT (id) DO NOTHING;
DROP TABLE IF EXISTS selection_reports;

INSERT INTO outreach_messages (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM deliveries
ON CONFLICT (id) DO NOTHING;
DROP TABLE IF EXISTS deliveries;

INSERT INTO payment_orders (id, tenant_id, idempotency_key, amount_fen, status, payload)
SELECT id, tenant_id, idempotency_key, amount_fen, status, payload FROM payments
ON CONFLICT (id) DO NOTHING;
DROP TABLE IF EXISTS payments;

INSERT INTO metric_snapshots (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM kpi_metrics
ON CONFLICT (id) DO NOTHING;
DROP TABLE IF EXISTS kpi_metrics;

INSERT INTO activation_jobs (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM recalls WHERE trigger = 'cold_start'
ON CONFLICT (id) DO NOTHING;
INSERT INTO recall_jobs (id, tenant_id, payload)
SELECT id, tenant_id, payload FROM recalls WHERE trigger = 'churn'
ON CONFLICT (id) DO NOTHING;
DROP TABLE IF EXISTS recalls;

ALTER TABLE leads DROP COLUMN IF EXISTS score_v2;

DELETE FROM schema_migrations WHERE version = '0001_postgres_shape';
