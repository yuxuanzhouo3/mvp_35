-- Restore quality_score from score_v2, then drop the expanded column.

ALTER TABLE leads ADD COLUMN IF NOT EXISTS quality_score numeric;
UPDATE leads SET quality_score = score_v2 WHERE quality_score IS NULL;
ALTER TABLE leads DROP COLUMN IF EXISTS score_v2;

DELETE FROM schema_migrations WHERE version = '0002_contract_score';
