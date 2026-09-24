# STAC-first multi-catalog data access

Status: accepted (2026-09-25, Phase 0)

We access all satellite data directly through STAC catalogs over
cloud-optimized GeoTIFFs — primarily Element84 Earth Search and Copernicus
Data Space Ecosystem, with USGS/NASA catalogs per sensor — and do not build on
Google Earth Engine. Each sensor adapter declares which catalog(s) it uses; no
catalog is a single point of failure.

## Why

- **$0 budget**: Earth Search serves Sentinel-2 L2A and Sentinel-1 GRD from
  non-requester-pays buckets with no auth; CDSE's free tier allows 12 TB/month
  transfer; NASA/USGS data is free. Windowed COG reads over HTTPS keep compute
  local and tiny.
- **"Maybe monetize" constraint**: Google Earth Engine's free tier is
  noncommercial-only and explicitly prohibits "charging or receiving a fee for
  Applications." All chosen sources (Copernicus, USGS, NASA) are licensed open
  for commercial use, so the access layer never blocks monetization.
- **No lock-in**: STAC is an open standard; catalogs are interchangeable behind
  the `SensorAdapter` interface. If one catalog dies, an adapter swaps its
  catalog — the rest of the system is untouched. (This is not hypothetical:
  Planetary Computer's team was laid off in 2024 and its Hub retired; we treat
  it as opportunistic, never load-bearing.)

## Considered options

- **B — Google Earth Engine**: single API + free server-side compute, but the
  free tier bars any future paid use of applications built on it, and its
  remote-compute model would hide the ingestion/processing pipeline that is the
  portfolio's core artifact. Rejected for the core path; allowed as an optional
  prototyping sandbox.
- **C — Hybrid**: in practice identical to A with GEE bolted on; rejected as
  needless complexity for a one-person system.

## Consequences

- The `SensorAdapter` interface is load-bearing infrastructure, not
  abstraction for its own sake — it exists because no single free catalog
  serves all four sensors.
- We maintain an auth matrix: Earth Search = anonymous; CDSE = OAuth2
  (10-min tokens); NASA Earthdata login = VIIRS/HLS/HyP3; MPC = anonymous SAS
  signing while it survives.
- **Known cost trap**: the canonical Landsat archive (`usgs-landsat` S3) is
  requester-pays. Landsat reads must go through a free HTTPS path (MPC-signed
  URLs or LandsatLook STAC) — never direct S3 without a signed/anonymous
  endpoint.
- Sentinel-1 analysis-ready data costs processing: primary path is ASF HyP3
  on-demand RTC (8,000 free credits/month ≈ 1,600 scenes at 30 m); MPC's
  `sentinel-1-rtc` collection is an opportunistic free alternative while MPC
  survives — adapters may prefer it, nothing may depend on it.
- MPC SAS terms prohibit sharing signed URLs with third parties: all provider
  reads happen server-side; clients receive rendered tiles and metrics only.

See `docs/research/data-access-verification.md` for cited facts.
