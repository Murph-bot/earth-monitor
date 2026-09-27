-- Daily per-AOI values from gridded sources that have no scenes: satellite
-- rainfall first (PDIR-Now), UV index next. One row per AOI, day, metric and
-- source; re-ingesting a day upserts.
CREATE TABLE daily_metrics (
    aoi_id      uuid NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    date        date NOT NULL,
    metric_name text NOT NULL,
    source      text NOT NULL REFERENCES sensors(id),
    value       double precision NOT NULL,
    unit        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aoi_id, metric_name, source, date)
);

ALTER TABLE sensors DROP CONSTRAINT sensors_kind_check;
ALTER TABLE sensors ADD CONSTRAINT sensors_kind_check
    CHECK (kind IN ('optical', 'sar', 'precipitation', 'uv'));

INSERT INTO sensors (id, name, kind, provider, license_text, resolution_m, revisit_days, enabled)
VALUES ('pdir-now', 'PDIR-Now satellite rainfall', 'precipitation', 'UC Irvine CHRS',
        'PDIR-Now rainfall, Center for Hydrometeorology and Remote Sensing, UC Irvine',
        4000, 1, true)
ON CONFLICT (id) DO NOTHING;

-- daily values have no scene: one notification per rule per day instead
ALTER TABLE notifications ADD COLUMN metric_date date;
CREATE UNIQUE INDEX notifications_rule_day_uniq
    ON notifications (alert_rule_id, metric_date) WHERE scene_id IS NULL;
