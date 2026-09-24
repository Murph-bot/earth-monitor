# Data-Access Verification — Earth-Observation Monitoring App

Verified against primary sources on **2026-09-25**. Every fact ends with its source. Anything that could not be confirmed is in the **UNVERIFIED** section at the end.

---

## 1. Microsoft Planetary Computer (MPC)

| Fact | Detail |
|---|---|
| Operational status | **Still operational.** STAC root catalog responds and a backend migration maintenance window completed 2026-09-22, indicating active operations (source: https://github.com/microsoft/PlanetaryComputer/discussions/504, https://planetarycomputer.microsoft.com/api/stac/v1) |
| Retirement status | **No announced retirement** of the free public data/APIs. The **Hub** (JupyterHub compute) was retired 2024-06-06; "the Planetary Computer Data and APIs will remain available and unchanged." (source: https://github.com/microsoft/PlanetaryComputer/discussions/347) |
| Caveat on longevity | MPC is explicitly a **Preview** product; "At any time and without notice, Microsoft may change or discontinue Previews." Microsoft launched a separate paid product, *Planetary Computer Pro* (Azure, public preview since ~Sept 2025). (source: https://raw.githubusercontent.com/microsoft/PlanetaryComputerDataCatalog/main/src/pages/Terms.js, https://azure.microsoft.com/en-us/blog/microsoft-planetary-computer-pro-unlocking-ai-powered-geospatial-insights-for-enterprises-across-industries/) |
| STAC endpoint | `https://planetarycomputer.microsoft.com/api/stac/v1` — STAC API 1.0.0, anonymous, no account required (source: https://planetarycomputer.microsoft.com/api/stac/v1, https://raw.githubusercontent.com/microsoft/PlanetaryComputerDataCatalog/main/docs/concepts/sas.md) |
| Relevant collections (verified live in `/collections`) | `sentinel-2-l2a`, `sentinel-1-grd`, `sentinel-1-rtc`, `landsat-c2-l1`, `landsat-c2-l2`, `hls2-l30`, `hls2-s30`, `cop-dem-glo-30`, `naip`, `esa-worldcover`, and 19 `modis-*-061` collections (e.g. `modis-09A1-061`, `modis-13A1-061`, `modis-43A4-061`, `modis-64A1-061`). **No `sentinel-2-l1c` collection** (only L2A). (source: https://planetarycomputer.microsoft.com/api/stac/v1/collections) |
| MODIS freshness problem | MPC MODIS ingestion has gaps since ~June 2025; some collections stalled or partially backfilled (open issue, last comments Dec 2025+). Treat MPC MODIS as unreliable for current monitoring. (source: https://github.com/microsoft/PlanetaryComputer/issues/453) |
| Sentinel-1 RTC freshness | `sentinel-1-rtc` items exist for 2026-09-24 (day before verification) including Sentinel-1D — actively updated, assets hosted in Azure blob `sentinel1euwestrtc` (source: live query to `.../collections/sentinel-1-rtc/items`) |
| Auth / signing | All blob assets require a SAS token since Oct 2024 (anonymous blob access was disabled on all storage accounts for security). Token endpoint: `GET /api/sas/v1/token/{collection_id}` or `/token/{storage_account}/{container}`; URL signing: `GET /api/sas/v1/sign?href={url}`; the `planetary-computer` Python package (`planetary_computer.sign`) automates signing + caching. No account needed to get a token. (source: https://github.com/microsoft/PlanetaryComputer/discussions/378, https://raw.githubusercontent.com/microsoft/PlanetaryComputerDataCatalog/main/docs/concepts/sas.md) |
| Rate limits | Rate limiting exists but is intentionally vague ("should be generous"). Throttling tier depends on whether requests come from Azure **West Europe** and whether a subscription key (`PC_SDK_SUBSCRIPTION_KEY`) is supplied. Anonymous users get the most-throttled tier; subscription keys (still issued per maintainer, Dec 2025) grant higher SAS-token rate limits and longer-lived tokens. (source: https://raw.githubusercontent.com/microsoft/PlanetaryComputerDataCatalog/main/docs/concepts/sas.md, https://github.com/microsoft/PlanetaryComputer/issues/464) |
| Terms of use / commercial | "Supplemental Terms of Use for Microsoft Planetary Computer Previews" (last updated Jan 2023): provided as-is, no SLA, max liability $10, "not meant for production use (though such use is not prohibited)." Maintainers state **commercial use is allowed** under those terms (source: https://github.com/microsoft/PlanetaryComputer/issues/435, https://planetarycomputer.microsoft.com/terms → source at https://raw.githubusercontent.com/microsoft/PlanetaryComputerDataCatalog/main/src/pages/Terms.js) |
| **Key contractual limit** | SAS **"Tokens may not be sublicensed to, distributed to, or shared with third parties"** (except staff/contractors working on your behalf). You cannot hand signed URLs to your web app's end users — proxy bytes through your backend, or point users at the source. Token authorized-use windows: Tier 1 up to 1 week, Tier 2 up to 6 months. (source: https://raw.githubusercontent.com/microsoft/PlanetaryComputerDataCatalog/main/src/pages/Terms.js) |

## 2. Element84 Earth Search

| Fact | Detail |
|---|---|
| Endpoint | `https://earth-search.aws.element84.com/v1` — STAC API 1.0.0, fully anonymous, verified live (source: https://earth-search.aws.element84.com/v1) |
| Version status | v1 is current; v0 deprecated long ago. `sentinel-2-c1-l2a` is the preferred S2 collection; the older `sentinel-2-l2a` collection still exists but has known gaps and is planned for deprecation/dropping once ESA Collection-1 backfill completes (source: https://github.com/Element84/earth-search/issues/44, https://element84.com/geospatial/introducing-earth-search-v1-new-datasets-now-available/) |
| Collections (verified live) | `sentinel-2-c1-l2a`, `sentinel-2-l1c`, `sentinel-2-l2a`, `sentinel-2-pre-c1-l2a`, `sentinel-1-grd`, `landsat-c2-l2`, `cop-dem-glo-30`, `cop-dem-glo-90`, `naip` (source: https://earth-search.aws.element84.com/v1) |
| Sentinel-2 C1 L2A assets | COGs at `https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/...` — **public HTTPS, no auth, us-west-2**; items fresh to 2026-09-24. ESA backfill gap: Nov 2016–Nov 2019 and 2022 incomplete (source: live item query; https://github.com/Element84/earth-search) |
| sentinel-2-l1c | `s3://sentinel-s2-l1c/...` JP2K originals — requester-pays bucket, eu-central-1 (source: live item assets; https://github.com/Element84/earth-search) |
| sentinel-2-l2a (legacy) | COG band assets public at `sentinel-cogs.s3.us-west-2` (no auth); some QA assets reference requester-pays `s3://sentinel-s2-l2a` (eu-central-1) (source: live item assets) |
| landsat-c2-l2 | Assets are `s3://usgs-landsat/...` — **requester-pays, us-west-2** (verified live). Earth Search merges USGS `landsat-c2l2-sr` + `landsat-c2l2-st`. (source: live item assets; https://registry.opendata.aws/usgs-landsat/) |
| sentinel-1-grd | Assets `s3://sentinel-s1-l1c/...` GRD-as-COG. Collection metadata says `storage:requester_pays: [true]`, `storage:region: eu-central-1` — **BUT live test shows anonymous HTTPS range reads succeed (HTTP 206)**, and the AWS Open Data registry lists the bucket as `RequesterPays: False`. i.e., free anonymous read works today via `https://sentinel-s1-l1c.s3.eu-central-1.amazonaws.com/...` (source: https://earth-search.aws.element84.com/v1/collections/sentinel-1-grd, https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/sentinel-1.yaml, live curl test 2026-09-25) |
| cop-dem-glo-30/90 | Public HTTPS, not requester-pays, eu-central-1 (source: collection `summaries.storage:*` fields) |
| naip | `s3://naip-analytic/...` requester-pays (source: live item assets) |
| Rate limits | **No published rate limits.** README: "This public API does not come with any guaranteed service." SNS topic for new items: `arn:aws:sns:us-west-2:608149789419:cirrus-es-prod-publish` (source: https://github.com/Element84/earth-search) |
| Terms of use | "Free-to-use" index of AWS Registry of Open Data; per-dataset licenses apply (Sentinel → Copernicus legal notice; Landsat → public domain). No SLA. (source: https://github.com/Element84/earth-search) |

## 3. Copernicus Data Space Ecosystem (CDSE)

| Fact | Detail |
|---|---|
| STAC endpoint | `https://stac.dataspace.copernicus.eu/v1` — live, STAC 1.0.0 + OGC API Features + CQL2 + collection-search (source: https://stac.dataspace.copernicus.eu/v1) |
| Collections (verified live, ~423 total) | `sentinel-2-l1c`, `sentinel-2-l2a`, `sentinel-2-gri-l1c`, `sentinel-2-global-mosaics`, `sentinel-1-grd`, `sentinel-1-slc`, `sentinel-1-slc-burst`, `sentinel-1-ocn`, `sentinel-1-global-mosaics`, full Sentinel-3 OLCI/SLSTR/SRAL/SYN sets, Sentinel-5P L2, `cop-dem-glo-30-dged-cog`, `cop-dem-glo-90-dged-cog`, `landsat-c2-l1-*` (L1 only, no L2 SR), and ~40 `modis-*` collections (e.g. `modis-terra-mod09a1`, `modis-terraaqua-mcd43a4`) (source: https://stac.dataspace.copernicus.eu/v1/collections) |
| Asset access via STAC | Item assets are `s3://eodata/...` references — require CDSE S3 credentials (free with account) or OData download with bearer token; not anonymous (source: live item query, 2026-09-25) |
| OData API | `https://catalogue.dataspace.copernicus.eu/odata/v1/Products` for search; download via `https://download.dataspace.copernicus.eu/odata/v1/Products(<id>)/$value` with Bearer token (source: https://documentation.dataspace.copernicus.eu/APIs/OData.html) |
| Auth flow | OAuth2/Keycloak: `POST https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`, `client_id=cdse-public`, `grant_type=password` (+`totp` if 2FA enabled). Access token lives 10 min; refresh within 60 min; max 100 sessions/account. (source: https://documentation.dataspace.copernicus.eu/APIs/Token.html) |
| Free quotas (Copernicus General User, verified in docs) | S3/OData/STAC: 2,000 req/min (S3), **4 concurrent connections**, **20 MB/s per connection**, **12 TB rolling-30-day transfer** (then 1 MB/s + 1 connection); Sentinel Hub APIs: 10,000 req/month, 10,000 PU/month, 300 PU/min; direct HTTP access to COGs: 50,000 req/month; openEO: 10,000 credits/month (temporary boost), 2 concurrent requests; Data Workspace: 0.1 TB/month, 25 processed products/month (source: https://documentation.dataspace.copernicus.eu/Quotas.html) |
| Accounts free | Yes — "Copernicus General user" is the free default tier; **no difference between EU and non-EU users** (source: https://documentation.dataspace.copernicus.eu/FAQ.html) |
| License | Copernicus Sentinel data: "free, full and open" under EU law — reproduction, distribution, communication, adaptation, and combination explicitly allowed (commercial use allowed). Required notice: **'Copernicus Sentinel data [Year]'**, or **'Contains modified Copernicus Sentinel data [Year]'** if modified (source: https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice, confirmed at https://documentation.dataspace.copernicus.eu/FAQ.html) |

## 4. USGS Landsat

| Fact | Detail |
|---|---|
| Collection 2 L2 status | Active — Earth Search `landsat-c2-l2` item found dated 2026-09-23; USGS landsatlook STAC lists `landsat-c2l2-sr` (surface reflectance) and `landsat-c2l2-st` (surface temperature) plus `landsat-c2l1`, ARD (`landsat-c2ard-*`), and L3 products (fSCA, BA, DSWE) (source: https://landsatlook.usgs.gov/stac-server/collections, live Earth Search item) |
| landsatlook STAC | `https://landsatlook.usgs.gov/stac-server` — official USGS STAC API (stac-server), STAC 1.1.0, upgraded to STAC API v1.0.0 in Feb 2026, actively maintained (source: https://landsatlook.usgs.gov/stac-server, https://www.usgs.gov/landsat-missions/spatiotemporal-asset-catalog-stac, https://www.usgs.gov/centers/eros/2026-02-04-landsat-stac-server-planned-maintenance) |
| AWS `usgs-landsat` bucket | `arn:aws:s3:::usgs-landsat/collection02/`, **us-west-2, REQUESTER-PAYS** — every byte out costs the caller (~$0.09/GB AWS egress + request fees). SNS topics for new scenes available. (source: https://registry.opendata.aws/usgs-landsat/) |
| M2M API | Machine-to-Machine API exists at `m2m.cr.usgs.gov` but requires a free EROS Registration System (ERS) account; login flow uses `login-token` → app token. Endpoint reachable (returns login page unauthenticated). (source: https://m2m.cr.usgs.gov/api/docs/reference/) |
| Google Cloud mirror | `gs://gcp-public-data-landsat` — **anonymous HTTPS works** (HTTP 200 on `index.csv.gz`, ~234 MB index, no auth needed). Free egress not guaranteed — GCS public buckets charge egress to the requester if requester-pays is enabled; this bucket is not requester-pays, so Google covers hosting, but heavy egress from public GCS buckets may hit egress fees depending on usage path — see UNVERIFIED. (source: live fetch of https://storage.googleapis.com/gcp-public-data-landsat/index.csv.gz) |
| License | "No restrictions on Landsat data downloaded from the USGS; it can be used or redistributed as desired." USGS requests a data-source statement; effectively public domain. (source: https://registry.opendata.aws/usgs-landsat/, license link https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/atoms/files/Landsat_Data_Policy.pdf) |

## 5. NASA Earthdata Cloud / CMR

| Fact | Detail |
|---|---|
| CMR | `https://cmr.earthdata.nasa.gov/search/` — full documented search API (source: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html) |
| CMR-STAC | `https://cmr.earthdata.nasa.gov/stac` — STAC 1.0.0 root with per-provider child catalogs: `LPCLOUD`, `LPCUMULUS`, `LAADS`, `POCLOUD`, `ASF`, `NSIDCV0`, `GESDISCCLD`, etc. (source: https://cmr.earthdata.nasa.gov/stac) |
| earthaccess | `earthaccess` Python lib (MIT), actively maintained — v0.19.0 released 2026-09-04; handles EDL auth, CMR search, S3 creds (source: https://earthaccess.readthedocs.io/en/latest/, https://api.github.com/repos/earthaccess-dev/earthaccess/releases/latest) |
| Earthdata Login | **Required for both HTTPS download and S3 access.** Free registration at urs.earthdata.nasa.gov. (source: https://nasa-openscapes.github.io/earthdata-cloud-cookbook/tutorials/Earthdata-cloud-clinic.html) |
| In-region constraint | Direct S3 access requires compute in **AWS us-west-2**; temporary S3 credentials expire after **1 hour** and are per-DAAC (e.g. `https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials`). HTTPS downloads work from anywhere but still need EDL. (source: https://nasa-openscapes.github.io/earthdata-cloud-cookbook/external/data_access_direct_S3.html, https://www.earthdata.nasa.gov/s3fs-public/2026-06/Answered_Q&A_HLS_Workshop_2026.pdf) |
| What's actually COG | **HLS (HLSL30_2.0, HLSS30_2.0)** on `LPCLOUD` are COGs. Standard MODIS land products (MOD09GA_061, MOD11A1_061, MYD*, MCD*, VNP09GA_002 on LP DAAC) are **HDF/NetCDF, not COGs** — cloud-hosted but not cloud-optimized; browsing/tiling them server-side requires decode. CMR-STAC `LPCLOUD` collections verified live. (source: https://cmr.earthdata.nasa.gov/stac/LPCLOUD/collections) |

## 6. MODIS / VIIRS mission status

| Fact | Detail |
|---|---|
| Terra MODIS | Science data collection ends **~Jan/Feb 2027** (NASA science article: end-of-science Feb 2027; instrument ops deck: End of Science March 1, 2027, decommission April 2027). Terra drifting since final inclination maneuver. (source: https://ladsweb.modaps.eosdis.nasa.gov/learn/modis-to-viirs-transition, https://science.nasa.gov/science-research/earth-science/terra-the-end-of-an-era/, https://modis.gsfc.nasa.gov/sci_team/meetings/202603/presentations/Session%201/Jones%20and%20Chiang%20-%20MODISInstOps_2026.pdf) |
| Aqua MODIS | Sources disagree slightly: ops presentation says expected decommissioning **August 2026**; LAADS transition doc says NASA plans to stop Aqua science collection **Sept 2027** (the "May 2, 2025" Earthdata alert says "late 2026/early 2027"). Treat Aqua MODIS as ending within ~12 months either way. (sources as above + https://www.earthdata.nasa.gov/data/alerts-outages/transition-from-modis-viirs) |
| Data right now | MODIS products still flowing: MOD09GA_061 granules dated 2026-09-20 in LPCLOUD (verified). Orbit drift already degrades data (earlier/later crossing times). Final reprocessing (Collection 8) expected complete ~Jan 2030. (source: live CMR-STAC query; LAADS transition doc) |
| VIIRS successor | VIIRS on SNPP, NOAA-20, NOAA-21 is the continuity path; NASA invested in continuity products. **No successor for Terra's morning orbit.** **SNPP data delivery ceases 2026-11-01** — migrate to NOAA-20/21 products now. (source: https://ladsweb.modaps.eosdis.nasa.gov/learn/modis-to-viirs-transition, LP DAAC site banner: https://lpdaac.usgs.gov/resources/e-learning/getting-started-with-cloud-native-harmonized-landsat-sentinel-2-hls-data-in-python/) |

## 7. Sentinel-1 analysis-ready access

| Fact | Detail |
|---|---|
| ASF HyP3 | Free **8,000 credits/month** per user (HyP3 Basic, NASA-funded), Earthdata login required. Costs: RTC 30 m = 5 cr (1,600 jobs/mo), RTC 20 m = 15 cr, RTC 10 m = 60 cr (~133 jobs/mo). Products expire after **14 days**, served via CloudFront. HyP3+ paid option: $0.05/credit, 30-day retention. More free credits possible by request "as budget allows." (source: https://hyp3-docs.asf.alaska.edu/hyp3-docs/using/credits/, https://hyp3-docs.asf.alaska.edu/about/) |
| Pre-computed RTC on MPC | `sentinel-1-rtc` collection on MPC = ASF RTC COGs mirrored in Azure, fresh to 2026-09-24 including Sentinel-1D — free with SAS signing (source: live query, https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-rtc/items) |
| GRD COGs (no self-processing) | Earth Search `sentinel-1-grd` → `sentinel-s1-l1c` bucket, **anonymous HTTPS verified working** (eu-central-1), includes S1A/S1B/S1C. GRD is not terrain-corrected (no RTC), but needs zero processing spend. (source: live tests, section 2) |
| CDSE S1 | `sentinel-1-grd`/`sentinel-1-slc` on CDSE require account + token/S3 creds (source: CDSE collections list) |

## 8. HLS (Harmonized Landsat Sentinel-2)

| Fact | Detail |
|---|---|
| Still produced | **Yes** — HLSS30_2.0 granules dated 2026-09-20 verified in CMR-STAC. v2.0 is current. (source: live query to https://cmr.earthdata.nasa.gov/stac/LPCLOUD/collections/HLSS30_2.0/items) |
| Collection IDs | `HLSL30_2.0` (Landsat, archive from Apr 2013), `HLSS30_2.0` (Sentinel-2, archive from Dec 2015), plus HLS-VI products. License CC0-1.0. On MPC mirrored as `hls2-l30`/`hls2-s30`. (source: https://cmr.earthdata.nasa.gov/stac/LPCLOUD/collections/HLSL30_2.0, MPC collections endpoint) |
| Latency | Official: ~1.7 days typical, "2–3 days" standard; constrained by atmospheric correction inputs. A low-latency (~6 h) HLS-LL product is in development, expected ~early 2027, not yet released. (source: https://hls.gsfc.nasa.gov/data-access-and-tools/, https://hls.gsfc.nasa.gov/hls-data/, https://www.earthdata.nasa.gov/s3fs-public/2026-06/Answered_Q&A_HLS_Workshop_2026.pdf) |
| Access | COGs in Earthdata Cloud (us-west-2) via LP DAAC; requires Earthdata Login for both HTTPS and S3; S3 direct access us-west-2-only with 1-h credentials. Also anonymously searchable/streamable via MPC's copy (SAS-signed). (sources as above + section 5) |

## 9. Google Earth Engine

| Fact | Detail |
|---|---|
| Free tier scope | Free for noncommercial use by: nonprofits, academic/teaching, news media, some government agencies (LDCs, Indigenous govts, scholarly research), trainers, and **"individual using Earth Engine for noncommercial purposes"**. Free users may NOT do fee-for-service work, may NOT "receive compensation for applications or data created by the use of Earth Engine," and may not do work on behalf of commercial entities. (source: https://earthengine.google.com/noncommercial/) |
| Free public web app? | A public app with zero revenue/donations likely qualifies as individual noncommercial; **any monetization (ads, payments, "monetization of services built on top of Earth Engine") = commercial**. (source: https://earthengine.google.com/noncommercial/) |
| NEW quota system | Since **2026-04-27** noncommercial projects get monthly EECU quotas (rolling out): **Community Tier 150 EECU-hr/mo** (default, no billing account), **Contributor Tier 1,000 EECU-hr/mo** (requires billing account, still free), **Partner Tier 100,000 EECU-hr/mo** (application + review, weeks). Over-quota → "restricted mode" (still runs, degraded). (source: https://developers.google.com/earth-engine/guides/noncommercial_tiers) |
| Other quotas | 40 concurrent standard + 40 high-volume requests per project, 100 req/s, batch concurrency by tier (noncommercial ~2 avg batch tasks), asset storage limits. (source: https://developers.google.com/earth-engine/guides/usage) |
| Commercial entry price | **Limited plan = usage fees only** (no monthly platform fee; pay per EECU); Basic $500/mo, Professional $2,000/mo. EECU on-demand: $1.33/online EECU-hr, $0.40/batch EECU-hr, $0.026/GB storage. (source: https://cloud.google.com/earth-engine/pricing) |
| Signup | **No waitlist** — self-serve: create Google Cloud project, enable EE API, register at `code.earthengine.google.com/register`, immediate access. (source: https://developers.google.com/earth-engine/guides/access) |

## 10. Key libraries — licensing + maintenance

| Library | License | Latest release / activity (verified via GitHub API 2026-09-25) |
|---|---|---|
| titiler (developmentseed/titiler) | MIT | v2.4.0, 2026-09-21 — active (source: https://github.com/developmentseed/titiler) |
| titiler-pgstac (stac-utils/titiler-pgstac) | MIT | v3.2.0, 2026-09-16 — active (source: https://github.com/stac-utils/titiler-pgstac) |
| titiler-cmr (developmentseed/titiler-cmr) | MIT | v1.1.3, 2026-09-22 — active (source: https://github.com/developmentseed/titiler-cmr) |
| pystac-client (stac-utils/pystac-client) | Apache-2.0 (LICENSE file) | v0.9.0, 2025-07-18 — maintained, slower cadence (source: https://github.com/stac-utils/pystac-client, https://raw.githubusercontent.com/stac-utils/pystac-client/main/LICENSE) |
| stackstac (gjoseph92/stackstac) | MIT | v0.5.1, **2024-08-10 — ~13 months stale**, last repo push same date (source: https://github.com/gjoseph92/stackstac) |
| rio-tiler (**cogeotiff/rio-tiler** — moved org) | BSD-3-Clause | v9.4.6, 2026-09-16 — active (source: https://github.com/cogeotiff/rio-tiler) |
| rasterio | BSD-3-Clause | v1.5.1, 2026-08-07 — active (source: https://github.com/rasterio/rasterio, pyproject `license = "BSD-3-Clause"`) |
| odc-stac (opendatacube/odc-stac) | Apache-2.0 | v0.5.3, 2026-07-29 — active (source: https://github.com/opendatacube/odc-stac) |
| earthaccess (earthaccess-dev/earthaccess) | MIT | v0.19.0, 2026-09-04 — active (source: https://github.com/earthaccess-dev/earthaccess) |
| planetary-computer SDK (microsoft/planetary-computer-sdk-for-python) | MIT | v1.0.0.post0, **2023-07-05 — dormant** but functional; commits as recent as 2025-05 (source: https://github.com/microsoft/planetary-computer-sdk-for-python) |

## 11. Free hosting reality check

| Service | Free tier (verified 2026-09-25) |
|---|---|
| Neon (now "from Databricks") | Free plan permanent: **0.5 GB storage/project**, 100 CU-hours/project/mo, scale-to-zero after 5 min (forced), 5 GB egress, 10 branches, PostGIS included, no credit card (source: https://neon.com/pricing) |
| Supabase | Free: **500 MB database**, 5 GB egress, 1 GB file storage, 50k MAU, unlimited API requests — **paused after 1 week inactivity**, max 2 active projects (source: https://supabase.com/pricing) |
| Vercel | Hobby $0: 100 GB bandwidth, 1M edge requests, 1M function invocations, 4h Fluid CPU — **non-commercial personal use only** (no ads, no donations, no monetization); can be shut down without notice per ToS (source: https://vercel.com/pricing, https://vercel.com/docs/limits/fair-use-guidelines, https://vercel.com/legal/terms) |
| Netlify | Free: **credit-based now** — 300 credits/mo; production deploys 15 cr each, bandwidth 20 cr/GB, web requests 2 cr/10k, compute 10 cr/GB-hr (source: https://www.netlify.com/pricing/) |
| Cloudflare Pages/Workers | Pages free: 500 builds/mo, 100 projects, unlimited static bandwidth. Workers free: **100k requests/day**, 10 ms CPU/invocation, **5 cron triggers/account** (cron on free, 15-min wall-clock max) (source: https://developers.cloudflare.com/pages/platform/limits/, https://developers.cloudflare.com/workers/platform/pricing/, https://developers.cloudflare.com/workers/platform/limits/) |
| Render | Still has free tier: Hobby $0 + free web service instances (512 MB, 0.1 CPU — sleep on idle), free static sites, 5 GB bandwidth/mo, free KV (25 MB). **Free Postgres only lasts 30 days**; cron jobs start at ~$1/mo. (source: https://render.com/pricing) |
| Fly.io | **Free tier dead** for new customers (plans discontinued Oct 2024); free trial = 2 VM-hours or 7 days, then credit card required; pay-as-you-go only (source: https://fly.io/docs/about/discontinued-plans/, https://fly.io/docs/about/free-trial/) |
| Railway | Free Trial ($5 one-time credit/30 days, no card) + a **Free plan $0/mo with $1/mo usage credit** (1 vCPU/0.5 GB, 1 replica, 3-day logs) (source: https://railway.com/pricing) |
| Cloudflare R2 | Free: **10 GB storage/mo, 1M Class A + 10M Class B ops/mo, zero egress fees** (all tiers) (source: https://developers.cloudflare.com/r2/pricing/) |
| GitHub Actions cron | Public repos: free/unlimited standard runners; private: 2,000 min/mo free. Min schedule interval 5 min but **best-effort (delayed at peak times)**; **auto-disabled after 60 days of repo inactivity** on public repos; 6-h max job time. ToS restricts use to activity related to the repo's software project — using it purely as a cron-as-a-service for an unrelated app is technically a ToS violation. (source: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax, https://docs.github.com/en/billing/concepts/product-billing/github-actions, https://docs.github.com/en/actions/reference/limits) |

---

## Red flags for a $0 budget

1. **Requester-pays buckets you must never hit directly from your own AWS creds without a payer account:** `usgs-landsat` (us-west-2), `sentinel-s2-l1c`, `sentinel-s2-l2a` QA assets, `naip-analytic`. Prefer the free-HTTPS alternatives: `e84-earth-search-sentinel-data` (S2 C1 L2A COGs), `sentinel-cogs`, and `sentinel-s1-l1c` (verified anonymously readable today despite Earth Search flagging it requester-pays — treat that as goodwill, not a contract).
2. **MPC SAS tokens cannot be shared with third parties** per its Supplemental Terms — you can't legally forward signed blob URLs to app users. Proxy through your backend (counts against your egress) or use sources with anonymous HTTP.
3. **MPC is a Preview with zero SLA and can be discontinued without notice**; its MODIS feed already stalled once (June 2025+). Don't make it your sole source.
4. **MODIS is dying:** Aqua ~Aug 2026, Terra ~early 2027; SNPP delivery ends **2026-11-01**. Plan on VIIRS (NOAA-20/21) or accept archive-only MODIS.
5. **CDSE downloads need a logged-in account** — your backend holds the token (10-min lifetime, refresh ≤60 min, ≤100 sessions). Sharing your account's throughput across all users caps you at 4 connections / 20 MB/s.
6. **Earthdata Cloud is us-west-2-only for S3** and every byte over HTTPS still needs EDL — a serverless frontend outside AWS cannot anonymously pull NASA COGs. Budget a proxy layer or use MPC mirrors for HLS.
7. **Free Postgres is tiny:** Neon 0.5 GB, Supabase 500 MB (and pauses after 1 week idle — bad for a cron-driven monitor that must stay warm), Render free Postgres dies after 30 days.
8. **Vercel Hobby forbids commercial use** (even donations/ads). If monetization is possible later, pick Cloudflare or Netlify free tiers, which have no non-commercial clause.
9. **GitHub Actions as a production scheduler** is ToS-gray (must relate to the repo's project) and silently disables after 60 days of repo inactivity. Cloudflare Workers cron (5 triggers free) is the cleaner $0 cron.
10. **GEE Community Tier (150 EECU-hr/mo)** is new (Apr 2026) and shared-compute — fine for experiments, risky as the sole backend for a public app; and one paid feature/user flips you to commercial.
11. **stackstac is effectively unmaintained** (last release Aug 2024) — prefer `odc-stac` + `xarray`, or `rio-tiler` for tiling.

## UNVERIFIED / could not confirm

- **Earth Search API rate limits** — Element84 publishes none; only "no guaranteed service" language. Actual throttle thresholds unknown.
- **GCP `gcp-public-data-landsat` egress cost model** — anonymous reads work (verified), but I did not find a primary-source statement on whether Google charges the requester for egress; assume it could bill the caller's GCP project for large transfers.
- **MPC anonymous rate-limit numbers** — only qualitative ("generous", tier depends on West-Europe origin + subscription key).
- **Exact Aqua decommission date** — NASA sources conflict (Aug 2026 vs Sept 2027).
- **Whether `sentinel-s1-l1c` will stay non-requester-pays** — AWS registry says RequesterPays: False and anonymous reads work today, but Earth Search metadata says requester_pays=true; could change.
- **Netlify free-plan commercial-use policy** — pricing page is silent on commercial use; their ToS historically allowed it on free tier but I did not re-confirm the current legal text.
