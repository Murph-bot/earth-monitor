# Sensor adapter plug-in plan

How each sensor slots into the `SensorAdapter` interface
(`backend/app/adapters/base.py`). One adapter = one row here + one module in
`app/adapters/` + registry entry. Verified facts: `docs/research/`.

## The interface contract

| Method | Contract |
|---|---|
| `search(aoi, start, end, max_cloud_cover, limit)` | STAC metadata search → `list[SceneMeta]`. Empty list is valid; API failures retry then raise `AdapterError`. |
| `read(scene, aoi, bands)` | Windowed COG reads clipped to the AOI → `SceneWindow`. Bands keep native grids; reproject the AOI per scene. |
| `quality_mask(window)` | Sensor-specific validity → bool `BandWindow` aligned to the finest science band. |
| `band_registry()` | `BandSpec` list: canonical names → catalog asset keys, with DN→physical scale/offset. |

## Per-sensor plan

| Sensor | Catalog / collection | Level | Quality mask | Special handling |
|---|---|---|---|---|
| **sentinel-2** ✅ built | Earth Search `sentinel-2-c1-l2a` (anonymous; CDSE fallback) | L2A surface reflectance | `scl` classes {4,5,6,7} valid | Bands mix 10/20/60 m grids; SCL mask reprojects to finest science grid |
| **landsat-8-9** | MPC `landsat-c2-l2` (SAS-signed) — **not** `usgs-landsat` S3 (requester-pays); LandsatLook STAC fallback | L2 SR + ST | `qa_pixel` bitfield: reject fill, dilated cloud, cirrus, cloud, shadow, snow | `lwir11` DN→K via raster:bands scale 0.00341802 / offset 149.0; orbit is WRS-2 path/row, not MGRS |
| **sentinel-1** | Search GRD: Earth Search `sentinel-1-grd` or CDSE. Pixels: ASF HyP3 RTC (primary) or MPC `sentinel-1-rtc` | RTC γ⁰ only — never raw GRD | Border-noise trim + γ⁰ validity range; no "cloud mask" exists | Metrics = backscatter change (dB); track orbit direction (asc/desc) — never mix in one series |
| **viirs** | NASA Earthdata Cloud `VNP09GA` daily SR (375–750 m) | L2 product | `SurfReflect_QF*` bitflags | Earthdata login; HTTPS reads fine anywhere, direct S3 needs us-west-2 — use HTTPS |

## Edge cases the layer owns

- **No scenes**: `search` returns `[]` — ingestion logs zero-found and moves on.
- **AOI across tiles/UTM zones**: `search` returns all intersecting scenes;
  `read` reprojects the AOI into each scene's CRS (Greece straddles UTM
  34N/35N — this is a real case, not theory). Mosaic happens at metric time.
- **Scene partially overlaps AOI**: `rasterio.mask` crops to overlap; pixels
  outside the data footprint read as nodata → masked invalid. This is why
  `valid_pixel_pct` exists.
- **Catalog failure/429**: `with_retry` exponential backoff (3 attempts),
  then `AdapterError` — ingestion marks the run failed and tries next cycle.
- **Missing asset key**: logged warning, band skipped, not a crash.

## How to add a sensor (checklist)

1. `app/adapters/<name>.py`: `SensorAdapter` subclass + `BANDS` registry.
2. Register in `registry.py`.
3. Unit tests for its quality-mask logic (the risky code); one env-gated
   integration test against the real catalog.
4. Row in this file + sensor row in the Phase 3 `sensors` table.
