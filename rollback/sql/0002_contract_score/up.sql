-- Contract: readers use score_v2. quality_score is removed only after the copy.

UPDATE leads SET score_v2 = quality_score WHERE score_v2 IS NULL AND quality_score IS NOT NULL;
ALTER TABLE leads DROP COLUMN IF EXISTS quality_score;

INSERT INTO schema_migrations (version) VALUES ('0002_contract_score')
ON CONFLICT (version) DO NOTHING;
