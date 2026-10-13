-- Live document table for the FastAPI modules.
-- The 4S catalog tables come from 20261001140000_pickglobal_core.sql.
-- Register, login, payment, selection, and acquisition still speak documents.
-- This table keeps those documents on the same remote PostgreSQL instance.
-- There is no RLS here: login looks up a user before a tenant is known,
-- and the application filters tenant_id on every later read.

CREATE TABLE documents (
  collection text NOT NULL,
  id text NOT NULL,
  tenant_id text,
  body jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  PRIMARY KEY (collection, id)
);

CREATE INDEX documents_collection_tenant ON documents (collection, tenant_id, created_at DESC);
