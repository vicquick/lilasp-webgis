# Architecture

## Render strategy — sandwich

Per-layer decision. Default = raster from QGIS Server.

| Layer profile | Engine | Endpoint |
|---|---|---|
| Pattern fills, base64 SVG markers, meter-units, multi-rule data-defined | `py-qgis-server` WMS | `/qgisserver/?MAP=<slug>&SERVICE=WMS` |
| Categorical / simple / scale-stable | `martin` + MapLibre style | `/tiles/<slug>/{z}/{x}/{y}` |
| Live edit / attribute queries | `py-qgis-server` WFS / WFS-T | `/qgisserver/?MAP=<slug>&SERVICE=WFS` |
| Print at desktop fidelity | `py-qgis-server` GetPrint | `/qgisserver/?MAP=<slug>&REQUEST=GetPrint&TEMPLATE=A4_Landscape` |
| Far future (view-only) | `qgis-js` WASM | `/static/qgis-js/…` |

## Dataflow

```
QGIS desktop  ───►  /srv/gis/<slug>/<project>.qgs
                          │
                          ▼
                    indexer (watchfiles)
                    ├─ parse_qgs_xml()
                    ├─ verify_capabilities() → py-qgis-server
                    ├─ write_metadata()      → PostgreSQL
                    ├─ emit_services_json()  → /srv/web/services.json
                    └─ if vector-eligible:
                       ogr2ogr → tippecanoe → PMTiles → /srv/tiles/
                       geostyler-cli QML → MapLibre style → /srv/tiles/

Browser
   │ GET /
   ▼
Traefik ──forward-auth──► Authentik (embedded outpost)
   │  (X-Authentik-Username, -Groups injected as response headers)
   ▼
web (nginx static + JS bundle)
   │
   ├─ GET /whoami        → auth-gateway (echoes headers as JSON)
   ├─ GET /services.json → static (emitted by indexer)
   ├─ GET /qgisserver/…  → py-qgis-server (Traefik strip prefix)
   └─ GET /tiles/…       → martin (Traefik strip prefix)
```

## Auth model

- Single Authentik application (`planportal`), one Provider in Forward-Auth mode.
- Project gating via Authentik groups in `X-Authentik-Groups` (pipe-separated, **not comma**).
- `auth-gateway` exposes `/whoami` for the SPA to read its user + groups.
- Indexer-managed `user_groups` table maps Authentik group → project slug → role (`viewer` / `editor` / `admin`).
- For ≤20 projects, we may also generate one Traefik router per project (cleaner audit trail). See ADR-0005.

## Indexer design — XML over PyQGIS

`xml.etree.ElementTree` extracts ≥95% of needed metadata from a `.qgs` without the 1 GB PyQGIS container. PyQGIS only invoked for periodic batch validation. Parse list:

- `<projectCrs>` → CRS
- `<ProjectViewSettings/Extent>` → bbox
- `<projectlayers/maplayer>` → layer tree (id, name, datasource, crs, type, wms-flag)
- `<visibility-presets>` → **map themes** (preserved verbatim from desktop)
- `<Layout>` → print layouts

## Vector-tile eligibility rule

Mark layer eligible iff:

1. Renderer ∈ `{singleSymbol, categorizedSymbol, graduatedSymbol, RuleRenderer}`
2. All symbol layers ∈ `{SimpleMarker, SimpleLine, SimpleFill, SimpleFillSymbolLayerV2}`
3. No `RenderMetersInMapUnits=1`
4. No `LinePatternFill`, `ShapeburstFill`, inverted polygon, diagram / heatmap / cluster

Otherwise fall back to WMS. See `services/indexer/src/indexer/eligibility.py`.

## CRS handling

`proj4` definitions for EPSG:25832 + DHDN Gauß-Krüger (31466/67/68) are baked into both:

1. `services/qgis-server/config/srs.db` (planned)
2. `services/web/src/lib/crs.ts` (proj4 strings — see source)

QGIS desktop projects address EPSG:25832 directly. The frontend reprojects to EPSG:3857 only for OSM/satellite backdrops.

## Memory caveats (py-qgis-server)

- Workers leak on QGIS rendering crashes. Always set `QGSRV_SERVER_MEMORY_HIGH_WATER_MARK=0.85`.
- Parallel rendering threads do not share memory pages. We run `workers=4, parallel-rendering=0` and horizontally scale.
- `STRICT_CHECK=yes` is brutal on large projects. Off in prod, nightly validation pass instead.
