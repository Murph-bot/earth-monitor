-- 0001_init.sql — earth-monitor schema
-- Conventions: uuid PKs on user-facing resources, bigint identity on
-- append-heavy tables, timestamptz everywhere, PostGIS geometry in EPSG:4326.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

CREATE TABLE schema_migrations (
    version     int PRIMARY KEY,
    name        text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- users: accounts. UUID because ids appear in URLs/JWTs — unguessable,
-- leak-safe. deleted_at = GDPR soft-delete (Phase 8 erasure flow).
CREATE TABLE users (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email       text NOT NULL UNIQUE,
    display_name text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

-- sensors: mirrors the adapter registry; exists as a table so the API can
-- answer "what can this system read" without importing adapter code.
CREATE TABLE sensors (
    id           text PRIMARY KEY,           -- 'sentinel-2'
    name         text NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('optical', 'sar')),
    provider     text NOT NULL,              -- 'ESA Copernicus'
    license_text text NOT NULL,              -- attribution shown in UI
    resolution_m numeric,
    revisit_days numeric,
    enabled      boolean NOT NULL DEFAULT true
);

-- collections: STAC-level groupings per catalog. A sensor may appear on
-- several catalogs (S2 on Earth Search AND CDSE fallback).
CREATE TABLE collections (
    id               text PRIMARY KEY,       -- 'sentinel-2-c1-l2a'
    sensor_id        text NOT NULL REFERENCES sensors(id),
    catalog          text NOT NULL,          -- 'earth-search'
    stac_url         text NOT NULL,
    processing_level text NOT NULL           -- 'L2A', 'RTC', ...
);

-- bands: queryable band registry per sensor (scale/dn_offset = DN→physical).
CREATE TABLE bands (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensor_id    text NOT NULL REFERENCES sensors(id),
    name         text NOT NULL,              -- 'red'
    asset_key    text NOT NULL,              -- STAC asset key
    kind         text NOT NULL CHECK (kind IN ('reflectance','thermal','quality','sar')),
    resolution_m numeric,
    scale        double precision NOT NULL DEFAULT 1.0,
    dn_offset    double precision NOT NULL DEFAULT 0.0,
    UNIQUE (sensor_id, name)
);

-- ---------------------------------------------------------------------------
-- aois: user-drawn monitoring polygons.
--   geom stored normalized to MultiPolygon — one type, no Polygon/MultiPolygon
--   branching anywhere downstream. bbox is a GENERATED column (ST_Envelope is
--   IMMUTABLE, so this is legal) — every list endpoint wants bounds, never pay
--   for the computation at read time. area_m2 is geodesic, computed at write.
CREATE TABLE aois (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       text NOT NULL,
    is_public  boolean NOT NULL DEFAULT false,
    geom       geometry(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    bbox       geometry(Polygon, 4326) GENERATED ALWAYS AS (ST_Envelope(geom)) STORED,
    area_m2    double precision NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX aois_geom_idx ON aois USING gist (geom);
CREATE INDEX aois_user_idx ON aois (user_id);

-- ---------------------------------------------------------------------------
-- scenes: cataloged acquisitions — METADATA ONLY. Pixels stay in provider
-- COGs; `assets` holds *unsigned* hrefs (MPC SAS is signed at read time,
-- and signed URLs never leave the backend — see ADR-0001).
-- UNIQUE (collection_id, scene_key) is the idempotency anchor: re-running
-- ingestion finds the same catalog id and upserts, never duplicates.
CREATE TABLE scenes (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collection_id text NOT NULL REFERENCES collections(id),
    sensor_id     text NOT NULL REFERENCES sensors(id),
    scene_key     text NOT NULL,             -- catalog item id
    acquired_at   timestamptz NOT NULL,
    cloud_cover   real,                      -- catalog-reported %, not our mask
    epsg          int,
    footprint     geometry(MultiPolygon, 4326) NOT NULL,
    bbox          geometry(Polygon, 4326) GENERATED ALWAYS AS (ST_Envelope(footprint)) STORED,
    assets        jsonb NOT NULL,
    properties    jsonb NOT NULL DEFAULT '{}',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (collection_id, scene_key)
);
CREATE INDEX scenes_footprint_idx ON scenes USING gist (footprint);
CREATE INDEX scenes_sensor_time_idx ON scenes (sensor_id, acquired_at DESC);

-- scene_aois: materialized scene↔AOI coverage. Computed once at ingestion
-- (ST_Intersection fraction) so API reads are a plain join, not a spatial op.
CREATE TABLE scene_aois (
    scene_id bigint NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    aoi_id   uuid   NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    coverage real   NOT NULL CHECK (coverage > 0 AND coverage <= 1),
    PRIMARY KEY (scene_id, aoi_id)
);
CREATE INDEX scene_aois_aoi_idx ON scene_aois (aoi_id);

-- ---------------------------------------------------------------------------
-- metrics: long-format per brief — one row per (aoi, scene, metric).
-- `date` duplicates acquired_at::date deliberately: the hot query is
-- "series for this aoi+metric over time" and a plain date column keeps it
-- a clean index scan. UNIQUE makes reprocessing an idempotent upsert.
CREATE TABLE metrics (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aoi_id          uuid NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    scene_id        bigint NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    sensor_id       text NOT NULL REFERENCES sensors(id),
    date            date NOT NULL,
    metric_name     text NOT NULL,           -- 'ndvi_mean', 'lst_mean', 'vv_db_change'
    value           double precision NOT NULL,
    unit            text NOT NULL,           -- 'index', 'kelvin', 'dB'
    valid_pixel_pct real NOT NULL CHECK (valid_pixel_pct BETWEEN 0 AND 1),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aoi_id, scene_id, metric_name)
);
CREATE INDEX metrics_series_idx ON metrics (aoi_id, metric_name, date);

-- ingestion_runs: one row per scheduled pipeline execution — the audit log
-- for "is ingestion alive and is it finding data".
CREATE TABLE ingestion_runs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensor_id       text NOT NULL REFERENCES sensors(id),
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    status          text NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'success', 'failed')),
    scenes_found    int NOT NULL DEFAULT 0,
    scenes_inserted int NOT NULL DEFAULT 0,
    metrics_written int NOT NULL DEFAULT 0,
    error           text
);
CREATE INDEX ingestion_runs_sensor_idx ON ingestion_runs (sensor_id, started_at DESC);

-- aoi_sensor_state: per-(AOI, sensor) ingestion watermark. `last_checked_at`
-- drives "did we look recently"; `last_scene_at` drives freshness displays.
CREATE TABLE aoi_sensor_state (
    aoi_id         uuid NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    sensor_id      text NOT NULL REFERENCES sensors(id),
    last_checked_at timestamptz,
    last_scene_at   timestamptz,
    PRIMARY KEY (aoi_id, sensor_id)
);

-- ---------------------------------------------------------------------------
-- alert_rules: conditions on metrics. `params` is JSONB because rule shapes
-- differ per rule_type ({op, value} for threshold; {window_days, sigma} for
-- baseline deviation) — a jsonb column beats a sparse matrix of nullable cols.
-- sensor_id NULL = evaluate on any sensor (enables S1 fallback rules).
CREATE TABLE alert_rules (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aoi_id               uuid NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    user_id              uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric_name          text NOT NULL,
    sensor_id            text REFERENCES sensors(id),
    rule_type            text NOT NULL CHECK (rule_type IN ('threshold', 'baseline_deviation')),
    params               jsonb NOT NULL,
    min_valid_pixel_pct  real NOT NULL DEFAULT 0.5,
    enabled              boolean NOT NULL DEFAULT true,
    created_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX alert_rules_aoi_idx ON alert_rules (aoi_id) WHERE enabled;

-- notifications: dispatched alerts on a channel. Status lifecycle:
-- queued -> sent | failed. The alert engine (Phase 8) writes; channel
-- senders (email, web push, later mobile push) read — same table, all channels.
CREATE TABLE notifications (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_rule_id bigint REFERENCES alert_rules(id) ON DELETE SET NULL,
    user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel       text NOT NULL CHECK (channel IN ('email', 'web_push', 'mobile_push')),
    title         text NOT NULL,
    body          text NOT NULL,
    payload       jsonb NOT NULL DEFAULT '{}',
    status        text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'failed')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    sent_at       timestamptz
);
CREATE INDEX notifications_user_idx ON notifications (user_id, status);

-- devices: reserved for Phase 9 mobile push tokens. web platform rows will
-- hold web-push endpoints — same table, same idea.
CREATE TABLE devices (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform   text NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    push_token text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz
);
CREATE INDEX devices_user_idx ON devices (user_id);
