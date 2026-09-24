# earth-monitor

Monitors Earth's surface over user-defined areas by turning scheduled satellite
observations into metric time series, alerts, and map tiles. API-first: all logic
lives in the backend; web and mobile clients are thin consumers of `/v1`.

## Language

### Geography

**AOI** (Area of Interest):
A user-owned polygon in GeoJSON/EPSG:4326 that the system monitors. Stored in
PostGIS, validated per `docs/aoi-standard.md`.
_Avoid_: region, zone, boundary, geometry (as a noun for AOIs)

**Scene**:
One satellite acquisition — a single dated observation of a footprint, identified
by a STAC Item. A scene may partially cover an AOI.
_Avoid_: image, tile, product, granule

### Data model

**Sensor**:
A satellite instrument family the system can ingest (e.g. `sentinel-2`,
`landsat-8-9`, `sentinel-1`, `viirs`). One row in `sensors`, one `SensorAdapter`
implementation.
_Avoid_: satellite, mission, platform (platforms carry sensors; the unit of
abstraction here is the data product)

**Collection**:
A STAC-level grouping of scenes from one sensor at one processing level
(e.g. `sentinel-2-c1-l2a`). A sensor may have several collections per catalog.
_Avoid_: dataset

**Catalog**:
A service hosting STAC collections (Earth Search, CDSE, Planetary Computer,
LPCLOUD). Each `SensorAdapter` declares which catalog(s) it binds to — catalogs
are interchangeable behind the adapter.
_Avoid_: provider, source (too broad — a source is the satellite program, a
catalog is the API we query)

**Band**:
A named spectral/channels asset within a scene (`red`, `nir`, `scl`, `vv`).
The `bands` registry table is per-sensor ground truth.
_Avoid_: channel, layer

**Metric**:
A single computed number for one (aoi, scene, metric_name) — e.g. `ndvi_mean`.
Long-format rows in `metrics`, always with `unit` and `valid_pixel_pct`.
_Avoid_: statistic, indicator, index (an index like NDVI is computed _per pixel_;
the metric is its AOI-level reduction)

### Extensibility

**Sensor Adapter**:
The plugin that knows how to search, read, and quality-mask one sensor's scenes.
Interface contract: `search / read / quality_mask / band_registry / metadata`.
_Avoid_: connector, driver, importer

**Analysis Module**:
The plugin that turns a scene's read window into metrics for an AOI
(e.g. NDVI, land surface temperature, SAR backscatter change). Sensor-agnostic
interface; declares which bands it needs.
_Avoid_: processor, algorithm, plugin (ambiguous — say which plugin type)

**Ingestion Run**:
One scheduled execution of the ingestion pipeline for one sensor, logged in
`ingestion_runs` with counts of scenes found/inserted/skipped.
_Avoid_: job, batch, sync

### Alerting

**Alert Rule**:
A user-defined condition on a metric (threshold, or deviation from rolling
baseline) attached to an AOI. Evaluated after each ingestion run.
_Avoid_: trigger, watcher, subscription

**Notification**:
A dispatched alert on a channel (email, web push, later mobile push). Same alert
engine feeds every channel.
_Avoid_: message, email

### Remote sensing vocabulary (defined once, used everywhere)

**STAC** (SpatioTemporal Asset Catalog): the metadata standard for finding scenes
and their asset URLs. All catalogs we use speak it.

**COG** (Cloud-Optimized GeoTIFF): GeoTIFF with internal tiling + overviews,
enabling HTTP range-reads of small windows instead of full downloads. The
entire $0 architecture depends on this.

**L1C / L2A / L2 / GRD / RTC**: processing levels. L1C = top-of-atmosphere
reflectance; L2A/L2 = bottom-of-atmosphere (surface) reflectance; GRD =
ground-range-detected SAR amplitude; RTC = radiometrically terrain-corrected
SAR backscatter (γ⁰), the analysis-ready SAR product. We only build on
analysis-ready levels.

**SCL** (Scene Classification Layer): Sentinel-2 L2A's per-pixel class mask
(cloud, shadow, vegetation, water…). Our cloud masking reads it, not raw bands.

**QA_PIXEL**: the Landsat/USGS equivalent quality band. Same role as SCL,
different encoding.

**valid_pixel_pct**: fraction of AOI pixels passing the quality mask for a
scene-metric pair. Everything downstream (charts, alerts) must respect it.
