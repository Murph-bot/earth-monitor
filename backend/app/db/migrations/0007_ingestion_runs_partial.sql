-- A sweep where some AOIs' catalog searches failed but others succeeded is
-- neither a clean success nor a total failure — 'partial' distinguishes it
-- so the audit log doesn't read as "ingestion is broken" every time one
-- user's AOI has a bad geometry. aois_failed counts how many.
ALTER TABLE ingestion_runs DROP CONSTRAINT ingestion_runs_status_check;
ALTER TABLE ingestion_runs ADD CONSTRAINT ingestion_runs_status_check
    CHECK (status IN ('running', 'success', 'partial', 'failed'));

ALTER TABLE ingestion_runs ADD COLUMN aois_failed int NOT NULL DEFAULT 0;
