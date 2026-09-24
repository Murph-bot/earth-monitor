# Cross-sensor harmonization rules

What "the same metric from different sensors" is allowed to mean — and what
it is not. Written at Phase 5, when NDVI/NDWI became real.

## Units

- **Adapters return physical units.** `read()` applies each band's
  `scale`/`dn_offset` from the band registry: Sentinel-2 → surface
  reflectance (`DN * 1e-4 - 0.1`), Landsat ST → kelvin, SAR → linear power.
  Analysis modules never see raw DN.
- Index modules additionally require **positive reflectance** per pixel —
  the DN offset pushes fill/edge pixels negative, and near-zero denominators
  otherwise explode ratios (caught live: one real scene read ndvi_mean = 10.7).

## Resolution & grids

- Bands keep their **native grids** through `read()` (S2 mixes 10/20/60 m).
  Alignment happens exactly once: `quality_mask()` puts the mask on the
  finest science band's grid.
- A module's `required_bands` **must share one grid** — mixing resolutions
  raises `AnalysisError`. Modules needing mixed bands are a Phase 5+
  problem (reproject explicitly, nearest for masks, bilinear for science).

## Comparability — the hard rule

**The same metric name across sensors is NOT the same measurement.** S2
"nir" (B08, 842 nm broad) and Landsat "nir" (B5, 865 nm narrow) differ in
bandwidth, center, resolution, and atmospheric correction lineage. An S2
NDVI and a Landsat NDVI for the same field can differ by several points.

Therefore:

1. `metrics.sensor_id` is part of a series' identity — never merge sensors
   into one chart without flagging it.
2. `valid_pixel_pct` semantics are uniform (fraction of AOI pixels valid),
   but validity *definition* is per-adapter (SCL classes vs QA_PIXEL bits).
3. For a true cross-sensor optical series, use **HLS v2.0** (HLSS30/HLSL30,
   LP DAAC) — NASA's harmonized product exists precisely to solve this and
   is verified active (~1.4-day median revisit, ~1.7-day latency, Earthdata
   login, CC0). Evaluate it as an adapter before writing any bandpass
   adjustment ourselves. See `docs/research/data-access-verification.md`.

## Deferred modules

Documented in `docs/adapter-plan.md`, blocked on their adapters:
Landsat LST (thermal, 100 m — native grid, never resample to 30 m optical),
Sentinel-1 backscatter change (RTC gamma0, dB units, orbit-direction splits),
VIIRS coarse context (375 m, different index validity ranges).
