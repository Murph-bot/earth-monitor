-- Landsat 8/9 goes live (Planetary Computer, anonymous SAS signing) for land
-- surface temperature. Blue and green are registered so a Landsat scene can
-- render as a truecolor tile like a Sentinel-2 one.
INSERT INTO bands (sensor_id, name, asset_key, kind, resolution_m, scale, dn_offset) VALUES
('landsat-8-9', 'blue',  'blue',  'reflectance', 30, 0.0000275, -0.2),
('landsat-8-9', 'green', 'green', 'reflectance', 30, 0.0000275, -0.2)
ON CONFLICT DO NOTHING;

UPDATE sensors SET enabled = true WHERE id = 'landsat-8-9';
