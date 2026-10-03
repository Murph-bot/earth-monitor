-- Unreadable scenes (broken/unreachable COG asset) used to retry forever —
-- every sweep re-downloaded the same dead asset, eating into the Actions
-- job's time budget. Track attempts per (scene, aoi) read; once the runner
-- gives up it records a 'read_error' gap so the pair stops being pending.
CREATE TABLE scene_read_failures (
    scene_id        bigint NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    aoi_id          uuid NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    attempts        int NOT NULL DEFAULT 0,
    last_error      text,
    last_attempt_at timestamptz,
    PRIMARY KEY (scene_id, aoi_id)
);

ALTER TABLE metric_gaps DROP CONSTRAINT metric_gaps_reason_check;
ALTER TABLE metric_gaps ADD CONSTRAINT metric_gaps_reason_check
    CHECK (reason IN ('no_data', 'no_valid_pixels', 'read_error'));
