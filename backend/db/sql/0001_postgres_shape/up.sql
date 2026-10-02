-- PickGlobal PostgreSQL shape. MVP is one instance.
-- Monthly partitions are a Business step; this migration keeps single tables
-- plus the indexes and tenant policies the contract needs.
-- Every change here has a matching down.sql.

CREATE TABLE tenants (
  id text PRIMARY KEY,
  name text NOT NULL,
  plan text,
  status text NOT NULL DEFAULT 'active',
  region text,
  shard_key text,
  feature_flags jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  email text,
  phone text,
  password_hash text,
  role text NOT NULL DEFAULT 'owner',
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'active', 'suspended', 'deleted')),
  region text,
  shard_key text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE roles (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_roles (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  user_id text NOT NULL,
  role_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  user_id text NOT NULL,
  refresh_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE password_resets (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  user_id text NOT NULL,
  token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  user_id text,
  action text NOT NULL,
  resource text NOT NULL,
  ip text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE payments (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  user_id text NOT NULL,
  provider text NOT NULL,
  amount bigint NOT NULL CHECK (amount > 0),
  currency text NOT NULL,
  status text NOT NULL
    CHECK (status IN ('created', 'pending', 'succeeded', 'failed', 'refunded')),
  external_id text,
  idempotency_key text NOT NULL,
  plan_id text,
  shard_key text,
  region text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE subscriptions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  plan text NOT NULL,
  status text NOT NULL,
  period_start timestamptz NOT NULL,
  period_end timestamptz NOT NULL,
  payment_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE invoices (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payment_id text NOT NULL,
  amount bigint NOT NULL,
  currency text NOT NULL,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE refunds (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payment_id text NOT NULL,
  amount bigint NOT NULL CHECK (amount > 0),
  currency text NOT NULL,
  status text NOT NULL,
  idempotency_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE coupons (
  id text PRIMARY KEY,
  tenant_id text,
  code text NOT NULL,
  amount_off bigint,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE payment_events (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payment_id text NOT NULL,
  external_id text NOT NULL,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tax_records (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  payment_id text,
  amount bigint,
  currency text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  source text NOT NULL,
  title text NOT NULL,
  sku text NOT NULL,
  price numeric,
  cost numeric,
  category text,
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  shard_key text,
  region text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE selection_reports (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  product_id text NOT NULL,
  route text,
  market text,
  profit_margin numeric,
  tax numeric,
  time_cost jsonb,
  risk text,
  score integer,
  status text NOT NULL
    CHECK (status IN ('draft', 'analyzing', 'completed', 'acquired')),
  rules_version text NOT NULL,
  seed_ready boolean NOT NULL DEFAULT false,
  metrics jsonb,
  ai_model_version text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE acquisition_tasks (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  report_id text,
  channel text NOT NULL,
  status text NOT NULL
    CHECK (status IN ('created', 'running', 'paused', 'completed', 'failed')),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE leads (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  task_id text,
  source text,
  name text,
  email text,
  phone text,
  company text,
  score integer,
  status text NOT NULL DEFAULT 'new'
    CHECK (status IN ('new', 'scored', 'qualified', 'contacted', 'replied', 'won', 'lost', 'recalled')),
  shard_key text,
  region text,
  compliance_region text,
  channel_id text,
  agency_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE campaigns (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  task_id text,
  channel text,
  subject text,
  content text,
  status text NOT NULL
    CHECK (status IN ('draft', 'pending_approval', 'approved', 'scheduled', 'sending', 'sent', 'paused', 'completed')),
  scheduled_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE deliveries (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  campaign_id text,
  lead_id text NOT NULL,
  channel text,
  status text NOT NULL,
  delivered_at timestamptz,
  opened_at timestamptz,
  replied_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE deals (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  lead_id text NOT NULL,
  amount numeric NOT NULL,
  currency text NOT NULL,
  status text NOT NULL,
  won_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE recalls (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  lead_id text NOT NULL,
  trigger text NOT NULL,
  recall_trigger text,
  status text NOT NULL
    CHECK (status IN ('triggered', 'queued', 'approved', 'delivered', 'sent', 'recovered', 'failed')),
  delivered_at timestamptz,
  recovered_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE kpi_metrics (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  metric_code text NOT NULL,
  value numeric,
  period text NOT NULL,
  kpi_period text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_calls (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  model text NOT NULL,
  prompt_version text NOT NULL,
  prompt_tokens integer NOT NULL DEFAULT 0,
  completion_tokens integer NOT NULL DEFAULT 0,
  latency_ms integer NOT NULL DEFAULT 0,
  status text NOT NULL,
  ai_model_version text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_models (
  id text PRIMARY KEY,
  name text NOT NULL,
  version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_prompts (
  id text PRIMARY KEY,
  version text NOT NULL,
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_embeddings (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  source_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_feedback (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  ai_call_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_cache (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  cache_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE events (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  event text NOT NULL,
  version text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dead_letters (
  id text PRIMARY KEY,
  tenant_id text,
  event text,
  version text,
  payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  job_type text NOT NULL,
  status text NOT NULL,
  idempotency_key text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE suppressions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  email text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_tenant_email ON users (tenant_id, email);
CREATE UNIQUE INDEX leads_tenant_email ON leads (tenant_id, email);
CREATE UNIQUE INDEX payments_idempotency ON payments (tenant_id, idempotency_key);
CREATE UNIQUE INDEX payment_events_external ON payment_events (external_id);
CREATE INDEX deliveries_campaign_lead ON deliveries (tenant_id, campaign_id, lead_id);
CREATE INDEX kpi_metrics_lookup ON kpi_metrics (tenant_id, metric_code, period);
CREATE INDEX ai_calls_tenant_created ON ai_calls (tenant_id, created_at);
CREATE INDEX audit_logs_tenant_created ON audit_logs (tenant_id, created_at);
CREATE INDEX products_attributes_gin ON products USING GIN (attributes);
CREATE INDEX selection_metrics_gin ON selection_reports USING GIN (metrics);

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users', 'roles', 'permissions', 'user_roles', 'sessions', 'password_resets', 'audit_logs',
    'payments', 'subscriptions', 'invoices', 'refunds', 'payment_events', 'tax_records',
    'products', 'selection_reports', 'acquisition_tasks', 'leads', 'campaigns', 'deliveries',
    'deals', 'recalls', 'kpi_metrics', 'ai_calls', 'ai_embeddings', 'ai_feedback', 'ai_cache',
    'events', 'jobs', 'suppressions'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))',
      t
    );
  END LOOP;
  EXECUTE 'ALTER TABLE tenants ENABLE ROW LEVEL SECURITY';
  EXECUTE 'ALTER TABLE tenants FORCE ROW LEVEL SECURITY';
  EXECUTE 'CREATE POLICY tenant_isolation ON tenants USING (id = current_setting(''app.tenant_id'', true)) WITH CHECK (id = current_setting(''app.tenant_id'', true))';
END $$;
