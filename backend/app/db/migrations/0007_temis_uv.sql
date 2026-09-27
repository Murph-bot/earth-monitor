-- Daily clear-sky UV index from KNMI TEMIS, a second daily_metrics source.
INSERT INTO sensors (id, name, kind, provider, license_text, resolution_m, revisit_days, enabled)
VALUES ('temis-uv', 'TEMIS clear-sky UV index', 'uv', 'KNMI / ESA',
        'TEMIS UV index, KNMI / ESA (Tropospheric Emission Monitoring Internet Service)',
        25000, 1, true)
ON CONFLICT (id) DO NOTHING;
