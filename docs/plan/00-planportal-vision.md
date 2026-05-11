# Planportal — Vision

> The webGIS we should have built first. Stop replacing QGIS — front it.

## Diagnosis of the previous attempt

The QWC2 stack (archived at `archive/qwc2-2026-04-16`) tried to vector-tile
everything and clone a QFieldCloud mirror as scope item #1. Two failure
modes compounded:

1. **MapLibre / OL style spec can't express LinePatternFill,
   RenderMetersInMapUnits, base64 SvgMarker, multi-rule data-defined
   `CASE`** — fidelity collapsed, workaround budget exploded, project
   stalled.
2. **QFieldCloud mirror as scope item #1** — too much. The lift killed
   momentum before we shipped a single useful tile.

## Reframe

Don't replace QGIS rendering — **front it**. WMS raster from QGIS Server
uses the same engine as QGIS Desktop, so it is pixel-identical by
definition. Promote layers to vector tiles only when they fit the
constraint. Default = raster.

## Stack (Coolify on Hetzner)

```
traefik ←forward-auth→ authentik
postgis · redis
py-qgis-server (3liz 1.9.6, Tornado + 0MQ, LRU project cache)
martin (PMTiles + PostGIS → MVT)
indexer (Python; watches /srv/gis/, parses .qgs)
auth-gateway (whoami sidecar, echoes Authentik headers)
web (raw OpenLayers + @masterportal/masterportalapi)
```

## Render strategy (per-layer decision)

| Profile | Engine | Endpoint |
|---|---|---|
| LL-WIE-style high-fidelity (base64 SVG, LinePatternFill, meter-units) | py-qgis-server WMS | `/qgisserver/?...` |
| Categorical / simple / scale-stable | martin + MapLibre style (geostyler-cli bake) | `/tiles/...` |
| Live edit / attribute query | py-qgis-server WFS / WFS-T | `/qgisserver/?...` |
| Print at desktop fidelity | py-qgis-server GetPrint with project's own layouts | `/qgisserver/?...&REQUEST=GetPrint` |
| Far future | qgis-js WASM | static |

## 5 UI pillars

1. **Project Picker** — grid of tiles (WMS thumbnail per project),
   Authentik-gated, search / recent.
2. **Map Canvas** — OL map, mixed sources.
3. **Project Tree + Themes** — mirrors QGIS Layer Tree node-for-node.
   Map-theme dropdown front and centre. "What you see in QGIS = what
   client sees" is the fidelity contract.
4. **Inspector (right rail)** — GFI, attribute table, GetPrint (PDF
   using desktop layouts), export, share-link signed 7d.
5. **Workspace tools** — measure, annotate, draw,
   comment-thread-on-feature (Postgres, ties to bimavo CDE later),
   snapshot, time-machine (git history of `.qgs`).

## Ingestion (indexer service)

Watches `/srv/gis/<project>/`. Accepts any of: `.qgs`/`.qgz`, QField
package zip, self-contained `shp + base64-QML` zip, `.gpkg` with
`layer_styles`. For raw zip → auto-generates a stub `.qgs`. Parses XML →
layer tree, map themes (`<visibility-presets>`), extents, CRS, print
layouts. Verifies `GetCapabilities`. Writes Postgres metadata + emits
`services.json` for the SPA. Vector-eligible layers → tippecanoe →
PMTiles → martin + geostyler-cli QML → MapLibre style.

## Phases

| Phase | Duration | Deliverables |
|---|---|---|
| 0 | 2 wks | Authentik + Traefik forward-auth, PostGIS, Redis, py-qgis-server, demo: LL-WIE-2427 zip → stub `.qgs` → WMS pixel-identical to desktop |
| 1 | 4-6 wks | Web SPA with Picker + Canvas + Tree + Theme dropdown, indexer v1, GetPrint export, single demo project live |
| 2 | quarter | Attribute table, comment plugin, share-link, measure, vector-tile path, per-project roles, mobile |
| 3 | later | bimavo CDE bridge, WFS-T edit, git-versioned projects, diff visualisation |
| 4 | 2027+ | qgis-js eject hatch — view-only projects render purely client-side, server free |

## Open questions

- masterportalAPI map-theme switcher: confirm per-layer `setVisible` works
  cleanly; otherwise ship a 50-line custom plugin (we already did, see
  `services/web/src/plugins/map-theme/`).
- Fonts in py-qgis-server container: bind-mount
  `/usr/share/fonts/custom/` with Futura PT etc. for CUX, else WMS
  labels degrade.
- Custom CRS end-to-end: verify CUX 25832 + Soldner Bessel survive into
  `services.json` and reproject correctly in the SPA.

## Explicit non-goals

- ❌ Full QFieldCloud mirror (out of scope; py-qgis-server covers 80%).
- ❌ Reimplementing QGIS rendering (we front it, we don't replace it).
- ❌ Symbol editor in browser (edit in QGIS desktop, ship the project).
- ❌ Vector tiles for everything (the previous failure mode).

## Sources

- [Dataport/POLAR](https://github.com/Dataport/polar) — research reference (we don't fork)
- [MasterPortal v3 docs](https://www.masterportal.org/mkdocs/doc/v3.2.2/)
- [py-qgis-server (3liz)](https://github.com/3liz/py-qgis-server) · [docs](https://docs.3liz.org/py-qgis-server/)
- [QFieldCloud architecture](https://docs.qfield.org/reference/qfieldcloud/architecture/)
- [Lizmap docs](https://docs.lizmap.com/)
- [qgis-js](https://github.com/qgis/qgis-js)
