-- PickGlobal PostgreSQL, project.md section 5.
-- MVP is one instance. tenant_id plus RLS. Money is integer fen or numeric, never float.
-- This version has down.sql. Leads and deliveries keep uniqueness across time,
-- so they are not month-partitioned. Audit logs and AI calls are partitioned
-- by created_at; the default partition holds MVP rows.
-- The running API still uses the JSON document store. Do not dual-write.

CREATE TABLE schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenants (
  id text PRIMARY KEY,
  name text NOT NULL,
  plan text NOT NULL DEFAULT 'free',
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active', 'suspended', 'deleted')),
  region text,
  compliance_region text,
  shard_key text,
  feature_flags jsonb NOT NULL DEFAULT '{"auth.sso":false,"auth.mfa":false,"payment.raas":false,"selection.auto_deal":false,"acquisition.social":false,"acquisition.ecommerce":false,"acquisition.expo":false,"acquisition.agency":false,"ai.agent":false,"ai.finetune":false,"digital_human":false,"geo_seo":false,"raas":false,"global_multi_active":false}'::jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz
);

CREATE TABLE users (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  email text,
  phone text,
  password_hash text,
  role text NOT NULL DEFAULT 'viewer' CHECK (role IN ('owner', 'admin', 'analyst', 'marketer', 'viewer')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'suspended', 'deleted')),
  display_name text,
  cloudbase_user_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE roles (
  id text PRIMARY KEY,
  tenant_id text REFERENCES tenants (id),
  code text NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE permissions (
  id text PRIMARY KEY,
  code text NOT NULL UNIQUE,
  resource text NOT NULL,
  action text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE role_permissions (
  role_id text NOT NULL REFERENCES roles (id),
  permission_id text NOT NULL REFERENCES permissions (id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  user_id text NOT NULL REFERENCES users (id),
  role_id text NOT NULL REFERENCES roles (id),
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE sessions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  user_id text NOT NULL REFERENCES users (id),
  token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE products (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  source text NOT NULL CHECK (source IN ('manual', 'csv', 'catalog')),
  title text NOT NULL,
  sku text NOT NULL,
  normalized_sku text NOT NULL,
  category text,
  target_price_usd numeric(18, 4),
  cost_cny numeric(18, 4),
  packaging_cny numeric(18, 4),
  domestic_freight_cny numeric(18, 4),
  international_freight_usd numeric(18, 4),
  price_currency text NOT NULL DEFAULT 'USD',
  cost_currency text NOT NULL DEFAULT 'CNY',
  origin_country text NOT NULL DEFAULT 'CN',
  target_market text NOT NULL DEFAULT 'US',
  route text NOT NULL DEFAULT 'CN-US',
  incoterm text NOT NULL DEFAULT 'DDP',
  tax_regime text NOT NULL DEFAULT 'cn_us',
  fx_usd_cny numeric(18, 4) NOT NULL DEFAULT 7.20,
  hs_code_hint text,
  context_version integer NOT NULL DEFAULT 1,
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE selection_reports (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  product_id text NOT NULL REFERENCES products (id),
  route text NOT NULL,
  market text NOT NULL,
  net_margin numeric(12, 6),
  net_profit_usd numeric(18, 4),
  tax numeric(18, 4),
  time_cost integer,
  risk text,
  score integer,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'analyzing', 'completed', 'acquired')),
  rules_version text NOT NULL,
  seed_ready boolean NOT NULL DEFAULT false,
  seed_analysis_id text,
  fx_usd_cny numeric(18, 4),
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  explanation text,
  explanation_model text,
  ai_model_version text,
  context_version integer,
  requested_at timestamptz,
  finished_at timestamptz,
  acquired_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE acquisition_tasks (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  report_id text REFERENCES selection_reports (id),
  channel text NOT NULL CHECK (channel IN ('ecommerce', 'social', 'expo', 'agency', 'enrichment', 'geo_seo', 'content_dh', 'cross_border', 'raas')),
  status text NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'running', 'paused', 'completed', 'failed')),
  started_at timestamptz,
  finished_at timestamptz,
  seed_analysis_id text,
  channel_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE leads (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  task_id text REFERENCES acquisition_tasks (id),
  source_channel text NOT NULL CHECK (source_channel IN ('ecommerce', 'social', 'expo', 'agency', 'enrichment', 'geo_seo', 'content_dh', 'cross_border', 'raas')),
  contact_name text,
  email text,
  phone text,
  company text,
  score integer CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
  score_v2 numeric,
  qualified boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'scored', 'qualified', 'contacted', 'replied', 'won', 'lost', 'recalled')),
  market text,
  platform text,
  dedupe_key text,
  seed_analysis_id text,
  exclude_from_ar boolean NOT NULL DEFAULT false,
  note text,
  opened_at timestamptz,
  replied_at timestamptz,
  won_at timestamptz,
  warmed_at timestamptz,
  agency_id text,
  channel_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE campaigns (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  task_id text REFERENCES acquisition_tasks (id),
  channel text CHECK (channel IS NULL OR channel IN ('ecommerce', 'social', 'expo', 'agency', 'enrichment', 'geo_seo', 'content_dh', 'cross_border', 'raas', 'email')),
  name text,
  purpose text CHECK (purpose IS NULL OR purpose IN ('acquisition', 'activation', 'recall')),
  subject text,
  content text,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'scheduled', 'sending', 'sent', 'paused', 'completed')),
  scheduled_at timestamptz,
  sent_at timestamptz,
  audience jsonb NOT NULL DEFAULT '{}'::jsonb,
  explanation_model text,
  ai_model_version text,
  agency_id text,
  channel_id text,
  seed_analysis_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE recalls (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  lead_id text NOT NULL REFERENCES leads (id),
  trigger text NOT NULL CHECK (trigger IN ('cold_start', 'churn')),
  recall_trigger text,
  status text NOT NULL DEFAULT 'triggered' CHECK (status IN ('triggered', 'queued', 'approved', 'delivered', 'recovered', 'failed')),
  reason text,
  draft text,
  enqueued_at timestamptz,
  delivered_at timestamptz,
  recovered_at timestamptz,
  warmed_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE deliveries (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  campaign_id text REFERENCES campaigns (id),
  lead_id text NOT NULL REFERENCES leads (id),
  recall_id text REFERENCES recalls (id),
  channel text CHECK (channel IS NULL OR channel IN ('ecommerce', 'social', 'expo', 'agency', 'enrichment', 'geo_seo', 'content_dh', 'cross_border', 'raas', 'email')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'delivered', 'bounced', 'complained', 'failed')),
  email text,
  body text,
  purpose text,
  ses_message_id text,
  delivered_at timestamptz,
  opened_at timestamptz,
  replied_at timestamptz,
  exclude_from_ar boolean NOT NULL DEFAULT false,
  channel_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE deals (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  lead_id text NOT NULL REFERENCES leads (id),
  amount_fen bigint NOT NULL CHECK (amount_fen >= 0),
  currency text NOT NULL DEFAULT 'CNY',
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'won', 'lost')),
  won_at timestamptz,
  agency_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE payments (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  user_id text REFERENCES users (id),
  provider text NOT NULL,
  amount_fen bigint NOT NULL CHECK (amount_fen >= 0),
  currency text NOT NULL DEFAULT 'CNY',
  status text NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'pending', 'succeeded', 'failed', 'refunded')),
  external_id text,
  idempotency_key text NOT NULL,
  plan_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE subscriptions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  plan text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('trialing', 'active', 'past_due', 'canceled')),
  period_start timestamptz,
  period_end timestamptz,
  raas_rule jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE invoices (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  payment_id text REFERENCES payments (id),
  number text,
  amount_fen bigint NOT NULL CHECK (amount_fen >= 0),
  currency text NOT NULL DEFAULT 'CNY',
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'issued', 'void')),
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE refunds (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  payment_id text NOT NULL REFERENCES payments (id),
  amount_fen bigint NOT NULL CHECK (amount_fen > 0),
  currency text NOT NULL DEFAULT 'CNY',
  status text NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'pending', 'succeeded', 'failed')),
  idempotency_key text NOT NULL,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE coupons (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  code text NOT NULL,
  amount_off_fen bigint CHECK (amount_off_fen IS NULL OR amount_off_fen >= 0),
  percent_off numeric(5, 2) CHECK (percent_off IS NULL OR (percent_off >= 0 AND percent_off <= 100)),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  expires_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE payment_events (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  payment_id text REFERENCES payments (id),
  provider text NOT NULL,
  external_id text,
  signature_ok boolean NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'ignored')),
  idempotency_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE tax_records (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  payment_id text REFERENCES payments (id),
  regime text NOT NULL,
  amount_fen bigint NOT NULL CHECK (amount_fen >= 0),
  currency text NOT NULL DEFAULT 'CNY',
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE ledger_entries (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  amount_fen bigint NOT NULL CHECK (amount_fen > 0),
  currency text NOT NULL DEFAULT 'CNY',
  subject text NOT NULL CHECK (subject IN ('usage', 'agency_commission', 'raas', 'reversal')),
  idempotency_key text NOT NULL,
  status text NOT NULL DEFAULT 'posted' CHECK (status IN ('posted')),
  signature text NOT NULL,
  agency_id text,
  raas_rule jsonb,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  reverses_id text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE jobs (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  job_type text NOT NULL,
  status text NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'running', 'paused', 'completed', 'failed')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb,
  error text,
  attempts integer NOT NULL DEFAULT 0,
  idempotency_key text,
  scheduled_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE kpi_metrics (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  metric_code text NOT NULL CHECK (metric_code IN ('N', 'ActR', 'TR', 'OR', 'AR', 'QR', 'ActR_cold', 'RecR', 'AnaT', 'LeadT', 'AcqT', 'ActT', 'RecT')),
  value numeric,
  period text NOT NULL,
  kpi_period text,
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE ai_models (
  id text PRIMARY KEY,
  provider text NOT NULL,
  name text NOT NULL,
  model_version text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_prompts (
  id text PRIMARY KEY,
  name text NOT NULL,
  prompt_version text NOT NULL,
  body text NOT NULL,
  model_id text REFERENCES ai_models (id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_calls (
  id text NOT NULL,
  tenant_id text NOT NULL REFERENCES tenants (id),
  model text NOT NULL,
  prompt_version text,
  prompt_tokens integer,
  completion_tokens integer,
  latency_ms integer,
  status text NOT NULL DEFAULT 'succeeded' CHECK (status IN ('succeeded', 'failed')),
  ai_model_version text,
  request jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text,
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE ai_calls_default PARTITION OF ai_calls DEFAULT;

CREATE TABLE ai_embeddings (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  source_table text NOT NULL,
  source_id text NOT NULL,
  model text NOT NULL,
  dims integer,
  embedding jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE ai_feedback (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  call_id text,
  rating integer,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE ai_cache (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  cache_key text NOT NULL,
  model text,
  prompt_version text,
  response jsonb NOT NULL DEFAULT '{}'::jsonb,
  expires_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE ai_conversations (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  title text,
  model text,
  prompt_version text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE ai_messages (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  conversation_id text NOT NULL REFERENCES ai_conversations (id),
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content text NOT NULL,
  model text,
  prompt_version text,
  prompt_tokens integer,
  completion_tokens integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE suppressions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  email text NOT NULL,
  reason text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE objects (
  id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  object_key text NOT NULL,
  content_hash text NOT NULL,
  mime text NOT NULL,
  byte_size bigint,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  shard_key text,
  region text,
  compliance_region text
);

CREATE TABLE audit_logs (
  id text NOT NULL,
  tenant_id text NOT NULL REFERENCES tenants (id),
  user_id text,
  action text NOT NULL,
  resource text NOT NULL,
  ip text,
  request_id text,
  summary jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  shard_key text,
  region text,
  compliance_region text,
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;

CREATE UNIQUE INDEX users_tenant_email ON users (tenant_id, email) WHERE email IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX users_cloudbase ON users (cloudbase_user_id) WHERE cloudbase_user_id IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX roles_system_code ON roles (code) WHERE tenant_id IS NULL;
CREATE UNIQUE INDEX roles_tenant_code ON roles (tenant_id, code) WHERE tenant_id IS NOT NULL;
CREATE UNIQUE INDEX user_roles_member ON user_roles (tenant_id, user_id, role_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX sessions_token ON sessions (token_hash);
CREATE UNIQUE INDEX products_sku ON products (tenant_id, normalized_sku) WHERE deleted_at IS NULL;
CREATE INDEX selection_reports_product ON selection_reports (tenant_id, product_id, created_at DESC);
CREATE UNIQUE INDEX leads_tenant_email ON leads (tenant_id, email) WHERE email IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX leads_dedupe ON leads (tenant_id, dedupe_key) WHERE dedupe_key IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX deliveries_campaign_lead ON deliveries (tenant_id, campaign_id, lead_id) WHERE campaign_id IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX deliveries_recall_lead ON deliveries (tenant_id, recall_id, lead_id) WHERE recall_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX deliveries_ses ON deliveries (ses_message_id);
CREATE UNIQUE INDEX payments_idempotency ON payments (tenant_id, idempotency_key) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX payments_external ON payments (provider, external_id) WHERE external_id IS NOT NULL;
CREATE UNIQUE INDEX refunds_idempotency ON refunds (tenant_id, idempotency_key) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX coupons_code ON coupons (tenant_id, code) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX payment_events_external ON payment_events (provider, external_id) WHERE external_id IS NOT NULL;
CREATE UNIQUE INDEX ledger_idempotency ON ledger_entries (tenant_id, idempotency_key);
CREATE UNIQUE INDEX jobs_idempotency ON jobs (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX jobs_status_scheduled ON jobs (status, scheduled_at);
CREATE UNIQUE INDEX kpi_metrics_period ON kpi_metrics (tenant_id, metric_code, period);
CREATE INDEX ai_calls_tenant_created ON ai_calls (tenant_id, created_at DESC);
CREATE UNIQUE INDEX ai_cache_key ON ai_cache (tenant_id, cache_key);
CREATE INDEX ai_messages_conversation ON ai_messages (tenant_id, conversation_id, created_at);
CREATE UNIQUE INDEX suppressions_email ON suppressions (tenant_id, email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX objects_key ON objects (tenant_id, object_key) WHERE deleted_at IS NULL;
CREATE INDEX audit_logs_tenant_created ON audit_logs (tenant_id, created_at DESC);

CREATE INDEX products_attributes_gin ON products USING gin (attributes);
CREATE INDEX selection_reports_metrics_gin ON selection_reports USING gin (metrics);
CREATE INDEX tenants_flags_gin ON tenants USING gin (feature_flags);
CREATE INDEX campaigns_audience_gin ON campaigns USING gin (audience);
CREATE INDEX jobs_payload_gin ON jobs USING gin (payload);
CREATE INDEX kpi_dimensions_gin ON kpi_metrics USING gin (dimensions);

CREATE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE FUNCTION reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only table %', TG_TABLE_NAME;
END;
$$;

CREATE FUNCTION ensure_month_partition(parent regclass, moment timestamptz) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
  start_ts timestamptz := date_trunc('month', moment);
  end_ts timestamptz := start_ts + interval '1 month';
  part_name text := format('%s_%s', parent, to_char(start_ts, 'YYYYMM'));
BEGIN
  IF to_regclass(part_name) IS NULL THEN
    EXECUTE format(
      'CREATE TABLE %I PARTITION OF %s FOR VALUES FROM (%L) TO (%L)',
      part_name, parent, start_ts, end_ts
    );
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', part_name);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))',
      part_name
    );
    EXECUTE format(
      'CREATE POLICY tenant_bypass ON %I USING (current_setting(''app.bypass_rls'', true) = ''on'') WITH CHECK (current_setting(''app.bypass_rls'', true) = ''on'')',
      part_name
    );
  END IF;
END;
$$;

-- touch_updated_at
DO $$
DECLARE
  tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'tenants',
    'users',
    'user_roles',
    'sessions',
    'products',
    'selection_reports',
    'acquisition_tasks',
    'leads',
    'campaigns',
    'recalls',
    'deliveries',
    'deals',
    'payments',
    'subscriptions',
    'invoices',
    'refunds',
    'coupons',
    'jobs',
    'kpi_metrics',
    'ai_cache',
    'ai_conversations',
    'suppressions',
    'objects'
  ]
  LOOP
    EXECUTE format(
      'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()',
      tbl || '_touch', tbl
    );
  END LOOP;
END;
$$;

-- append_only
DO $$
DECLARE
  tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'payment_events',
    'tax_records',
    'ledger_entries',
    'ai_calls',
    'ai_embeddings',
    'ai_feedback',
    'ai_messages',
    'audit_logs'
  ]
  LOOP
    EXECUTE format(
      'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION reject_mutation()',
      tbl || '_append_only', tbl
    );
  END LOOP;
END;
$$;

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenants
  USING (id = current_setting('app.tenant_id', true))
  WITH CHECK (id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_bypass ON tenants
  USING (current_setting('app.bypass_rls', true) = 'on')
  WITH CHECK (current_setting('app.bypass_rls', true) = 'on');

ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY role_read ON roles
  USING (tenant_id IS NULL OR tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id IS NOT NULL AND tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_bypass ON roles
  USING (current_setting('app.bypass_rls', true) = 'on')
  WITH CHECK (current_setting('app.bypass_rls', true) = 'on');

-- tenant_rls
DO $$
DECLARE
  tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'users',
    'user_roles',
    'sessions',
    'products',
    'selection_reports',
    'acquisition_tasks',
    'leads',
    'campaigns',
    'recalls',
    'deliveries',
    'deals',
    'payments',
    'subscriptions',
    'invoices',
    'refunds',
    'coupons',
    'payment_events',
    'tax_records',
    'ledger_entries',
    'jobs',
    'kpi_metrics',
    'ai_calls',
    'ai_embeddings',
    'ai_feedback',
    'ai_cache',
    'ai_conversations',
    'ai_messages',
    'suppressions',
    'objects',
    'audit_logs'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))',
      tbl
    );
    EXECUTE format(
      'CREATE POLICY tenant_bypass ON %I USING (current_setting(''app.bypass_rls'', true) = ''on'') WITH CHECK (current_setting(''app.bypass_rls'', true) = ''on'')',
      tbl
    );
  END LOOP;
END;
$$;

ALTER TABLE ai_calls_default ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ai_calls_default
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_bypass ON ai_calls_default
  USING (current_setting('app.bypass_rls', true) = 'on')
  WITH CHECK (current_setting('app.bypass_rls', true) = 'on');

ALTER TABLE audit_logs_default ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON audit_logs_default
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_bypass ON audit_logs_default
  USING (current_setting('app.bypass_rls', true) = 'on')
  WITH CHECK (current_setting('app.bypass_rls', true) = 'on');

INSERT INTO permissions (id, code, resource, action) VALUES
  ('perm_catalog_read', 'catalog.read', 'catalog', 'read'),
  ('perm_catalog_write', 'catalog.write', 'catalog', 'write'),
  ('perm_report_read', 'report.read', 'report', 'read'),
  ('perm_report_write', 'report.write', 'report', 'write'),
  ('perm_lead_read', 'lead.read', 'lead', 'read'),
  ('perm_lead_write', 'lead.write', 'lead', 'write'),
  ('perm_campaign_send', 'campaign.send', 'campaign', 'send'),
  ('perm_billing_read', 'billing.read', 'billing', 'read'),
  ('perm_billing_write', 'billing.write', 'billing', 'write'),
  ('perm_kpi_read', 'kpi.read', 'kpi', 'read'),
  ('perm_audit_read', 'audit.read', 'audit', 'read');

INSERT INTO roles (id, tenant_id, code, name) VALUES
  ('role_owner', NULL, 'owner', '所有者'),
  ('role_admin', NULL, 'admin', '管理员'),
  ('role_analyst', NULL, 'analyst', '分析'),
  ('role_marketer', NULL, 'marketer', '营销'),
  ('role_viewer', NULL, 'viewer', '只读');

INSERT INTO role_permissions (role_id, permission_id)
SELECT 'role_owner', id FROM permissions
UNION ALL
SELECT 'role_admin', id FROM permissions;

INSERT INTO role_permissions (role_id, permission_id)
SELECT 'role_viewer', id FROM permissions WHERE action = 'read';

INSERT INTO role_permissions (role_id, permission_id) VALUES
  ('role_analyst', 'perm_catalog_read'),
  ('role_analyst', 'perm_catalog_write'),
  ('role_analyst', 'perm_report_read'),
  ('role_analyst', 'perm_report_write'),
  ('role_analyst', 'perm_lead_read'),
  ('role_analyst', 'perm_kpi_read'),
  ('role_marketer', 'perm_lead_read'),
  ('role_marketer', 'perm_lead_write'),
  ('role_marketer', 'perm_campaign_send'),
  ('role_marketer', 'perm_report_read');

INSERT INTO schema_migrations (version) VALUES ('0001_core');
