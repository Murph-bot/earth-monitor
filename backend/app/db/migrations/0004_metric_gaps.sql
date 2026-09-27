-- metric_gaps: a (scene, aoi, metric) the analysis looked at and could not
-- compute — the AOI sits outside the scene's data, or every pixel over it
-- is masked (cloud, shadow, snow). Without this row the pair stays pending
-- and every sweep re-downloads the same unusable imagery. Read failures are
-- not gaps: they stay pending and retry.
CREATE TABLE metric_gaps (
    aoi_id      uuid NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    scene_id    bigint NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    metric_name text NOT NULL,
    reason      text NOT NULL CHECK (reason IN ('no_data', 'no_valid_pixels')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aoi_id, scene_id, metric_name)
);
