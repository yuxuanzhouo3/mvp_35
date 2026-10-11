-- Shared hot cache for the API instances.
-- This PostgreSQL environment cannot open the document database, and a
-- separate Redis instance is another bill. Rows live on the PostgreSQL
-- already attached to the CloudBase environment. A read ignores a row
-- once expires_at has passed.

CREATE TABLE cache_entries (
  key text PRIMARY KEY,
  value text NOT NULL,
  expires_at timestamptz NOT NULL
);

CREATE INDEX cache_entries_expires_at ON cache_entries (expires_at);
