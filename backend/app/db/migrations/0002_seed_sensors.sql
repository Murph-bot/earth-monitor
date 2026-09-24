-- 0002_seed_sensors.sql — sensor/collection/band catalog seed.
-- Mirrors the adapter registries so the API can describe capabilities from
-- the DB alone. Keep in sync when adapters land.

INSERT INTO sensors (id, name, kind, provider, license_text, resolution_m, revisit_days, enabled) VALUES
('sentinel-2',  'Sentinel-2 MSI (A/B/C)', 'optical', 'ESA Copernicus',
 'Contains modified Copernicus Sentinel data [year]', 10, 5, true),
('landsat-8-9', 'Landsat 8/9 OLI+TIRS', 'optical', 'USGS/NASA',
 'USGS Landsat data courtesy of the U.S. Geological Survey', 30, 8, false),
('sentinel-1',  'Sentinel-1 SAR (A/C/D)', 'sar', 'ESA Copernicus',
 'Contains modified Copernicus Sentinel data [year]; RTC via ASF HyP3', 10, 6, false),
('viirs',       'VIIRS (NOAA-20/21)', 'optical', 'NASA/NOAA',
 'NASA VIIRS data courtesy of NASA LANCE/LP DAAC', 375, 1, false);

INSERT INTO collections (id, sensor_id, catalog, stac_url, processing_level) VALUES
('sentinel-2-c1-l2a', 'sentinel-2', 'earth-search',
 'https://earth-search.aws.element84.com/v1', 'L2A'),
('sentinel-2', 'sentinel-2', 'cdse',
 'https://stac.dataspace.copernicus.eu/v1', 'L2A'),
('landsat-c2-l2', 'landsat-8-9', 'planetary-computer',
 'https://planetarycomputer.microsoft.com/api/stac/v1', 'L2'),
('sentinel-1-grd', 'sentinel-1', 'earth-search',
 'https://earth-search.aws.element84.com/v1', 'GRD'),
('sentinel-1-rtc', 'sentinel-1', 'planetary-computer',
 'https://planetarycomputer.microsoft.com/api/stac/v1', 'RTC'),
('VNP09GA', 'viirs', 'nasa-earthdata', 'https://cmr.earthdata.nasa.gov/stac/LPCLOUD', 'L2');

INSERT INTO bands (sensor_id, name, asset_key, kind, resolution_m, scale, dn_offset) VALUES
('sentinel-2', 'blue',     'blue',     'reflectance', 10, 0.0001, -0.1),
('sentinel-2', 'green',    'green',    'reflectance', 10, 0.0001, -0.1),
('sentinel-2', 'red',      'red',      'reflectance', 10, 0.0001, -0.1),
('sentinel-2', 'rededge1', 'rededge1', 'reflectance', 20, 0.0001, -0.1),
('sentinel-2', 'nir',      'nir',      'reflectance', 10, 0.0001, -0.1),
('sentinel-2', 'nir08',    'nir08',    'reflectance', 20, 0.0001, -0.1),
('sentinel-2', 'swir16',   'swir16',   'reflectance', 20, 0.0001, -0.1),
('sentinel-2', 'swir22',   'swir22',   'reflectance', 20, 0.0001, -0.1),
('sentinel-2', 'scl',      'scl',      'quality',     20, 1.0, 0.0),
('landsat-8-9', 'red',      'red',      'reflectance', 30, 0.0000275, -0.2),
('landsat-8-9', 'nir',      'nir08',    'reflectance', 30, 0.0000275, -0.2),
('landsat-8-9', 'swir16',   'swir16',   'reflectance', 30, 0.0000275, -0.2),
('landsat-8-9', 'lwir',     'lwir11',   'thermal',    100, 0.00341802, 149.0),
('landsat-8-9', 'qa_pixel', 'qa_pixel', 'quality',    30, 1.0, 0.0),
('sentinel-1', 'vv', 'vv', 'sar', 10, 1.0, 0.0),
('sentinel-1', 'vh', 'vh', 'sar', 10, 1.0, 0.0),
('viirs', 'red', 'SurfReflect_I1', 'reflectance', 375, 1.0, 0.0),
('viirs', 'nir', 'SurfReflect_I2', 'reflectance', 375, 1.0, 0.0),
('viirs', 'qf',  'SurfReflect_QF2', 'quality', 375, 1.0, 0.0);
