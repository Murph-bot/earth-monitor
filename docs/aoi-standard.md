# AOI standard

How areas of interest are represented, validated, and stored. This contract is
what lets one user-drawn polygon work unchanged across four sensors with
different native projections.

## On the wire

- **Format**: GeoJSON `Feature` per RFC 7946. A `FeatureCollection` containing
  exactly one Feature is accepted and unwrapped.
- **Geometry**: `Polygon` required; `MultiPolygon` accepted (stored, treated as
  one logical AOI). Points/lines rejected — a monitoring AOI must have area.
- **CRS**: EPSG:4326 (WGS84, lon/lat degrees) always. RFC 7946 mandates it;
  clients never send anything else, so there is no CRS negotiation.
- **Vertex order**: right-hand rule (exterior ring counter-clockwise). We
  normalize on ingest rather than reject — web draw tools are inconsistent.
- **`properties`**: reserved for `name` (string, ≤ 120 chars) and
  `is_public` (bool, default false). Everything else ignored, not stored.

## Validation rules (enforced at API boundary)

| Rule | Limit | Rationale |
|---|---|---|
| Max area | 100 km² | Free-tier guardrail: bounds pixel reads and metric compute; revisit if real use demands more |
| Min area | 4 × sensor min pixel (≈ 400 m² for S2) | Sub-pixel AOIs produce meaningless metrics |
| Self-intersection | Rejected | PostGIS `ST_IsValid`; invalid geometry poisons spatial queries |
| Vertex count | ≤ 2,000 | Pathological polygons blow up masking cost for zero benefit |
| Latitude | −60°…75° | Sentinel-2 coverage band; keeps UTM reprojection honest |

## In the database

- Stored as `geometry(Polygon|MultiPolygon, 4326)` via PostGIS — never as raw
  JSON. Spatial queries (`ST_Intersects`, `ST_Area`) need the real type.
- Denormalized `bbox` column + `area_m2` (geodesic, `ST_Area(geography)`)
  cached at write time — both are read on nearly every request.
- GiST spatial index on the geometry column.

## In the pipeline

- Adapters receive the AOI in EPSG:4326 and reproject to each scene's native
  UTM zone (read from the STAC item's `proj:epsg`) for masking/stats. One AOI,
  N projections — never the reverse.
- Scenes are matched to AOIs by footprint intersection at ingestion; the match
  is stored so a scene landing on several AOIs is processed once, mapped many.

## Why this standard (teaching note)

EO data lives in dozens of projections (Sentinel-2 = 60 UTM zones, Landsat =
its own grid, SAR = range geometry). Picking **one** wire format (GeoJSON/4326)
and pushing all projection complexity into the adapter keeps the API, the
database, and every client simple — the complexity lives exactly where the
sensor-specific knowledge already has to exist.
