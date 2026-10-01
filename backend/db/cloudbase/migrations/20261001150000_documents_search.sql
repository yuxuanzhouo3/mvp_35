-- Search index for product and lead documents.
-- The application matches name, sku, email, and id. This index keeps that
-- lookup on the documents table as the library grows.

CREATE INDEX documents_search_idx ON documents USING gin (
  to_tsvector(
    'simple',
    coalesce(body->>'name', '') || ' ' ||
    coalesce(body->>'sku', '') || ' ' ||
    coalesce(body->>'email', '') || ' ' ||
    id
  )
);
