# Sensor comparison matrix

Scope: the four sources in the project brief, verified 2026-09-25.
Greece/SE Europe is the launch region, so revisit figures are given for ~38–40°N.

## At a glance

| | Sentinel-2 MSI | Landsat 8+9 (OLI+TIRS) | Sentinel-1 SAR | VIIRS (MODIS → legacy) |
|---|---|---|---|---|
| Resolution | 10 m (RGB/NIR), 20 m (red-edge/SWIR), 60 m (coastal) | 30 m optical; thermal 100 m native (delivered at 30 m) | ~10 m px, IW mode | I-bands 375 m, M-bands 750 m |
| Revisit @ ~39°N | ~2–3 days effective (2–3 satellites + swath overlap); nominal 5-day repeat | 8 days combined (16-day each, offset by 8) | ~4–6 days (S-1A + S-1C + S-1D; S-1B lost Dec 2021) | Daily (per satellite) |
| Bands/channels | 13 (coastal → SWIR) | 11, incl. 2 thermal infrared | C-band SAR, VV+VH | 22 bands incl. thermal & day/night band |
| Cloud sensitivity | Blocked | Blocked | Immune — all-weather, day/night | Mostly blocked; TIR partially through thin cloud |
| Product we use | L2A (surface reflectance + SCL mask) | L2 (surface reflectance + surface temp) | RTC γ⁰ (from GRD via HyP3) | L2 products (VNP*) |
| Processing burden | Low — arrives analysis-ready | Medium — QA_PIXEL masks, scale factors | High — speckle, orbit direction, RTC needed | Low — arrives as products |
| Free access path | Earth Search `sentinel-2-c1-l2a` (anon, free COGs); CDSE fallback | Planetary Computer `landsat-c2-l2` (SAS-signed HTTPS); LandsatLook STAC; **NOT** `usgs-landsat` S3 (requester-pays) | Earth Search `sentinel-1-grd` (anonymous reads verified live) or CDSE for GRD; ASF HyP3 **or** MPC `sentinel-1-rtc` for analysis-ready | NASA Earthdata Cloud (LP DAAC/LAADS), CMR-STAC |
| License | Copernicus: free/open, commercial OK, attribution required | USGS public domain, attribution requested | Copernicus: free/open | NASA open data |
| Best-fit use cases | Vegetation (NDVI), water (NDWI), burn scars, urban growth | Heat/thermal, 40+ yr archive (L5→L9), HLS pairing with S2 | Flood mapping, cloud-gap fallback, soil-moisture proxy, structure change | Daily regional context, active fire (FIRMS), coarse trends |

## Watch items (things that changed or will)

- **MODIS is ending**: Aqua stops science collection ~Sep 2026 (possible
  extension to Fall 2027); Terra end-of-science ~Mar 2027, decommission Apr
  2027. We therefore spec the adapter for **VIIRS** (SNPP data delivery ceases
  2026-11-01, but NOAA-20/21 continue) and treat MODIS as a historical archive
  only.
- **Sentinel-2C is operational** (launched Sep 2024) — HLS now reports ~1.4-day
  global median cloud-free revisit across L8/L9/S2. Plan for three S2 streams.
- **Planetary Computer is unmaintained** (team laid off 2024, Hub retired June
  2024) — API still serves, so use it for Landsat while it lives, with
  LandsatLook/GCS mirror as documented fallback.
- **HLS** (HLSS30/HLSL30 v2.0, LP DAAC, Earthdata login, ~1.7–3-day latency)
  solves optical cross-sensor harmonization for free — revisit in Phase 5
  before writing any harmonization code ourselves.
- **Sentinel-1D is operational** — MPC `sentinel-1-rtc` shows fresh S-1D items
  (verified 2026-09-24). Constellation is now 1A+1C+1D; S-1B permanently dead
  (Dec 2021). Never assume 6-day *paired* coverage exists in the archive before
  a given commissioning date.

## Trade-off notes

- Sentinel-2 is the right primary adapter: highest free resolution, best
  revisit for Greece, simplest quality mask (SCL), and the only source with a
  fully anonymous free COG catalog (Earth Search).
- Sentinel-1's value is *coverage when optical fails*, not resolution parity —
  its module should produce change/backscatter metrics, not pretend to be
  NDVI.
- VIIRS replaces MODIS's role (daily regional context). At 375–750 m it is
  context, not measurement, for typical AOIs — useful for alerts like fire and
  for "no clear pixel in 30 days" explanations.
