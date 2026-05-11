# Planportal — Research Brief

> **Stack target:** POLAR (OpenLayers) + py-qgis-server (WMS/WFS/GetPrint) + martin/PMTiles + Authentik forward-auth + PostGIS + Redis + a Python indexer service watching `/srv/gis/<project>/`.
>
> Cited from upstream docs and source code, May 2026.

---

## 1. POLAR plugin contract

POLAR is a **Vue 2 + Vite 5 + Nx 22** monorepo (Dataport, EUPL-1.2) layered on `@masterportal/masterportalapi` (peer-dep pinned at **2.48.0**). The `@polar/core` package re-exports the masterportalAPI surface and adds three things: `createMap`, `addPlugins`, and the `NineLayout` 3×3 layout grid. ([repo](https://github.com/Dataport/polar), [gettingStarted.md](https://github.com/Dataport/polar/blob/main/gettingStarted.md))

### Plugin signature (verified from `packages/plugins/*/src/index.ts`)

Every shipped plugin (`AddressSearch`, `Legend`, `Gfi`, `Draw`, `Export`, `Pins`, `IconMenu`, …) follows the same two-arg curried contract:

```ts
// packages/plugins/Legend/src/index.ts (verbatim)
import Vue from 'vue'
import { LegendConfiguration } from '@polar/lib-custom-types'
import { Legend } from './components'
import locales from './locales'

export default (options: LegendConfiguration) => (instance: Vue) =>
  instance.$store.dispatch('addComponent', {
    name: 'legend',
    plugin: Legend,
    locales,
    options,
  })
```

Plugins with side-effecting state add a `storeModule` (Vuex module factory — see `Gfi/src/index.ts`):

```ts
import { makeStoreModule } from './store'
export default (options: GfiConfiguration) => (instance: Vue) =>
  instance.$store.dispatch('addComponent', {
    name: 'gfi',
    plugin: Gfi,
    locales,
    storeModule: makeStoreModule(),
    options,
  })
```

### masterportalAPI hooks (`@polar/core/src/utils/addPlugins.ts`)

```ts
let initialCreateMap = null
export default function addPlugins(this, plugins) {
  const originalCreateMap = this.createMap
  if (!initialCreateMap) initialCreateMap = originalCreateMap
  this.createMap = async (params) => {
    const instance = await originalCreateMap(params)
    plugins.forEach((initializePlugin) => initializePlugin(instance))
    return instance
  }
}
```

So plugins are invoked **after** the masterportalAPI builds the map. They receive the Vue root, which already has Vuex (`instance.$store`) and an OpenLayers `Map` reachable via `instance.$store.getters.map`. Subscriptions to plugin state use the namespaced pattern `plugin/<name>/<getter>` — e.g. `plugin/zoom/zoomLevel`, `plugin/loadingIndicator/addLoadingKey`.

### Skeleton for a custom Planportal plugin

This is a minimal "GetPrint launcher" plugin that emits a print URL when the user clicks. Drop into `packages/plugins/GetPrint/`:

```ts
// src/index.ts
import Vue from 'vue'
import GetPrint from './components/GetPrint.vue'
import locales from './locales'
import { makeStoreModule } from './store'

export interface GetPrintOptions {
  printService: string        // e.g. https://webgis.planportal.de/print
  layoutName: string          // matches a print layout in the .qgs
  layoutTag: string           // NineLayoutTag value
}

export default (options: GetPrintOptions) => (instance: Vue) =>
  instance.$store.dispatch('addComponent', {
    name: 'getPrint',
    plugin: GetPrint,
    locales,
    storeModule: makeStoreModule(options),
    options,
  })
```

```vue
<!-- src/components/GetPrint.vue -->
<template>
  <button class="polar-plugin-getprint" @click="launch">
    {{ $t('plugins.getPrint.button') }}
  </button>
</template>
<script>
export default {
  name: 'GetPrint',
  methods: {
    async launch() {
      const url = await this.$store.dispatch('plugin/getPrint/buildUrl')
      window.open(url, '_blank')
    },
  },
}
</script>
```

```ts
// src/store/index.ts
export const makeStoreModule = (options) => ({
  namespaced: true,
  state: () => ({ ...options }),
  actions: {
    async buildUrl({ rootGetters, state }) {
      const map = rootGetters.map
      const [w, h] = map.getSize()
      const extent = map.getView().calculateExtent([w, h])
      const params = new URLSearchParams({
        SERVICE: 'WMS', REQUEST: 'GetPrint',
        TEMPLATE: state.layoutName,
        FORMAT: 'pdf',
        'map0:EXTENT': extent.join(','),
        CRS: 'EPSG:25832',
      })
      return `${state.printService}?${params}`
    },
  },
})
```

### Client registration (verbatim pattern from Snowbox)

```ts
// addPlugins.ts
import { setLayout, NineLayout, NineLayoutTag } from '@polar/core'
import GetPrint from '@planportal/plugin-getprint'
import LayerChooser from '@polar/plugin-layer-chooser'
import IconMenu from '@polar/plugin-icon-menu'

export const addPlugins = (core) => {
  setLayout(NineLayout)
  core.addPlugins([
    IconMenu({
      menus: [
        { plugin: LayerChooser({}), icon: 'fa-layer-group', id: 'layerChooser' },
        { plugin: GetPrint({
            printService: '/qgisserver',
            layoutName: 'A4_Querformat',
            layoutTag: NineLayoutTag.TOP_RIGHT,
          }), icon: 'fa-print', id: 'getPrint' },
      ],
      layoutTag: NineLayoutTag.TOP_RIGHT,
      initiallyOpen: 'layerChooser',
    }),
  ])
}
```

```ts
// polar-client.ts
import polarCore from '@polar/core'
import { addPlugins } from './addPlugins'
import { mapConfiguration } from './mapConfiguration'

addPlugins(polarCore)
polarCore.rawLayerList.initializeLayerList(
  '/services.json',           // <- emitted by our indexer
  (layerConf) => polarCore.createMap({
    containerId: 'polarstern',
    mapConfiguration: { ...mapConfiguration, layerConf },
  }),
)
```

### Build/bundle story

The monorepo uses Nx 22 + Vite 5 with a shared `viteConfigs/getClientConfig.ts`. Each client lives in `packages/clients/<name>/` with its own `vite.config.js` extending the shared config. `npm run snowbox` boots dev for the demo client; `nx build @polar/client-planportal` produces a `dist/` consumable as `@polar/client-generic`. Our **Planportal client** should fork from `snowbox` and live as `packages/clients/planportal/`. Plugins published as `@planportal/plugin-<name>` go on a private registry (`.npmrc`).

### Limitations vs MasterPortal

POLAR is **a slice of masterportalAPI plus a plugin wrapper** — not full MasterPortal v3. You **do not** get:
- MasterPortal's `config.json` / `config-master.json` topic tree
- MasterPortal's full v3 admin/portal config UI
- 3D / Cesium views (Cesium is a devDep of POLAR but not wired into the generic client)
- MasterPortal's full GFI templates (POLAR ships its own simpler Gfi plugin)
- Print frontend (MasterPortal has a full layout-configurable print UI — POLAR ships nothing; we must build the GetPrint plugin against py-qgis-server's GetPrint endpoint)
- WPS/Routing addons beyond OpenRouteService

The arcana doc explicitly warns: **masterportalAPI does not follow SemVer** — every bump requires a full API check. POLAR pins to a single version (`2.48.0`) and the build runs `scripts/overrideMasterportalapi.js` to patch upstream behaviour. ([arcana.md](https://github.com/Dataport/polar/blob/main/arcana.md))

---

## 2. py-qgis-server production config

`3liz/qgis-map-server:1.9.x` (current release as of May 2026 is **1.9.6**). Repo ships a `DEPRECATION_NOTICE.md` pointing to **QJazz** as the next-gen successor — but py-qgis-server is still receiving 1.9.x fixes and is the right choice today. ([docs.3liz.org](https://docs.3liz.org/py-qgis-server/), [3liz/py-qgis-server](https://github.com/3liz/py-qgis-server))

### Worker model

Architecture: a **Tornado** HTTP front (`qgisserver --proxy`) accepting requests, dispatching over **0MQ DEALER/ROUTER** to N worker processes (`qgisserver-worker`). Workers may be local or remote; they self-register against the proxy — zero-config scale-out. Fair queueing, per-request timeout (`QGSRV_SERVER_TIMEOUT`), auto-restart when worker exceeds memory watermark.

The known **memory-leak trap**: parallel rendering threads in QGIS Server do **not** share memory pages — a 60 MB GeoJSON × 4 parallel renders = 8 GB resident. For prod, prefer many small worker containers (workers=1–2, parallel-rendering off) horizontally scaled over few big workers with parallel rendering on. ([discussion](https://github.com/kartoza/docker-qgis-server/issues/22))

### Key env vars (from [configuration.html](https://docs.3liz.org/py-qgis-server/configuration.html))

| Var | Default | Purpose |
|---|---|---|
| `QGSRV_SERVER_HTTP_PORT` | 8080 | HTTP port |
| `QGSRV_SERVER_WORKERS` | 2 | Number of 0MQ workers |
| `QGSRV_SERVER_TIMEOUT` | 20 | Per-request timeout |
| `QGSRV_SERVER_HTTP_PROXY` | no | **Set yes behind Traefik** — honours X-Forwarded-* |
| `QGSRV_SERVER_PROXY_URL` | – | Public URL — fixes GetCapabilities `OnlineResource` |
| `QGSRV_SERVER_MEMORY_HIGH_WATER_MARK` | 0.9 | Worker self-restarts at 90 % RSS |
| `QGSRV_CACHE_SIZE` | 10 | LRU max projects in memory |
| `QGSRV_CACHE_ROOTDIR` | – | Project root (we mount `/srv/gis`) |
| `QGSRV_CACHE_STRICT_CHECK` | yes | Validate layers on cache load |
| `QGSRV_CACHE_CHECK_INTERVAL` | 0 | >0 = async refresh, ≤0 = check every request |
| `QGSRV_CACHE_PRELOAD_CONFIG` | – | Static-cache project list file |
| `QGSRV_CACHE_ALLOW_STORAGE_SCHEMES` | `*` | Allowlist for `file:`, `postgresql:`, aliases |
| `QGSRV_TRUST_LAYER_METADATA` | no | Skip per-load layer validation (big speedup) |
| `QGSRV_DISABLE_GETPRINT` | no | Skip print-layout discovery (faster cold-load) |
| `QGSRV_SERVER_GETFEATURELIMIT` | -1 | Hard cap on WFS feature count |
| `QGSRV_SERVER_PLUGINPATH` | – | QGIS Server plugin dir |
| `QGSRV_MANAGEMENT_ENABLED` | no | REST mgmt API on `:19876` |

### Project addressing & per-project access

Projects are addressed via the `MAP=` query param. Schemes: `file:` (relative to `CACHE_ROOTDIR`), `postgresql:` (QGIS-in-Postgres), plus aliases configured under `[projects.schemes]`. ([schemes.html](https://docs.3liz.org/py-qgis-server/schemes.html))

```ini
# Per-project alias — exposes only what we want
[projects.schemes]
public=file:/srv/gis/public/
internal=file:/srv/gis/internal/
```

Auth is **not in py-qgis-server**. Enforce per-project access at the Traefik layer: route `/qgisserver/?...&MAP=public:...` to one middleware chain and `MAP=internal:...` to another. Practical approach: emit one Traefik router per project from the indexer (matching `Path(\`/qgisserver/<slug>\`)` with `StripPrefix` + URL rewrite to inject `MAP=`).

### Custom fonts + custom CRS

The entrypoint sets `QGIS_CUSTOM_CONFIG_PATH=$HOME=/home/qgis` and copies any source config tree into `$HOME` ([entrypoint](https://github.com/3liz/py-qgis-server/blob/master/docker/docker-entrypoint.sh)). To add fonts, bind-mount `/usr/share/fonts/custom/` and the QGIS rendering pipeline picks them up via fontconfig. Custom CRS / `srs.db` overrides go into `$HOME/QGIS/QGIS3/profiles/default/resources/`.

### docker-compose.yml snippet

```yaml
services:
  qgisserver:
    image: 3liz/qgis-map-server:1.9.6
    environment:
      QGSRV_SERVER_WORKERS: "4"
      QGSRV_SERVER_TIMEOUT: "60"
      QGSRV_SERVER_HTTP_PROXY: "yes"
      QGSRV_SERVER_PROXY_URL: "https://webgis.planportal.de/qgisserver"
      QGSRV_SERVER_MEMORY_HIGH_WATER_MARK: "0.85"
      QGSRV_CACHE_SIZE: "30"
      QGSRV_CACHE_ROOTDIR: /srv/gis
      QGSRV_CACHE_CHECK_INTERVAL: "300"
      QGSRV_CACHE_STRICT_CHECK: "no"
      QGSRV_TRUST_LAYER_METADATA: "yes"
      QGSRV_LOGGING_LEVEL: INFO
      QGIS_SERVER_PARALLEL_RENDERING: "0"   # see memory caveat
    volumes:
      - /srv/gis:/srv/gis:ro
      - /srv/gis-fonts:/usr/share/fonts/custom:ro
      - qgis-home:/home/qgis
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.qgis.rule=Host(`webgis.planportal.de`) && PathPrefix(`/qgisserver`)"
      - "traefik.http.routers.qgis.middlewares=authentik-auth@file,qgis-strip"
      - "traefik.http.middlewares.qgis-strip.stripprefix.prefixes=/qgisserver"
      - "traefik.http.services.qgis.loadbalancer.server.port=8080"
volumes:
  qgis-home:
```

---

## 3. martin + PMTiles + geostyler-cli

### Martin (`ghcr.io/maplibre/martin:1.9.1`)

Rust tile server, sources: PostGIS (auto-discovery of geometry tables and `function_zxy(z,x,y)` SQL functions), MBTiles (with directory hot-reload), PMTiles (local file, http(s), and S3-compatible: MinIO, R2, Hetzner). ([Martin docs](https://maplibre.org/martin/), [config-file.md](https://github.com/maplibre/martin/blob/main/docs/content/config-file/index.md), [sources-files.md](https://github.com/maplibre/martin/blob/main/docs/content/sources-files.md))

Important: **PMTiles in Martin has no built-in auth.** Access control must be enforced upstream (Traefik forward-auth). Serving PMTiles directly from S3 (without Martin) bypasses any access control and is a known egress-cost / DoS risk per the Martin docs.

### Config example (`config.yaml`)

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/maplibre/martin/main/schemas/config.json
listen_addresses: '0.0.0.0:3000'
worker_processes: 4
cache:
  size_mb: 512

postgres:
  connection_string: '${DATABASE_URL}'
  default_srid: 25832
  pool_size: 10
  auto_publish:
    tables: { from_schemas: [public] }

pmtiles:
  sources:
    cuxhaven_base:    file:///srv/tiles/cuxhaven/base.pmtiles
    cuxhaven_overlay: file:///srv/tiles/cuxhaven/overlay.pmtiles
    frankfurt_base:   file:///srv/tiles/frankfurt/base.pmtiles
```

URL pattern: `https://webgis.planportal.de/tiles/{source_id}/{z}/{x}/{y}` (+ TileJSON at `/{source_id}`, catalog at `/catalog`). Reverse-proxy under `/tiles/` via Traefik StripPrefix.

### PMTiles storage layout (matching `/srv/gis/<project>/`)

```
/srv/tiles/
  <project>/
    base.pmtiles            # always-on background
    overlay.pmtiles         # composited overlay (per map theme)
    <theme>.pmtiles         # one per QGIS map theme (visibility-preset)
    <theme>.style.json      # MapLibre style emitted by indexer
```

The indexer emits one `*.pmtiles` per **map theme**, not per layer — that's how POLAR/MapLibre composes overlays cleanly.

### geostyler-cli QML → MapLibre style

```bash
npm i -g geostyler-cli
# Per QML next to the .qgs
geostyler-cli -s qml -t mapbox \
  -o /srv/tiles/cuxhaven/overlay.style.json \
  /srv/gis/cuxhaven/styles/overlay.qml

# Directory batch
geostyler-cli -s qml -t mapbox \
  -o /srv/tiles/cuxhaven/ \
  /srv/gis/cuxhaven/styles/
```

Source parsers: `mapbox`, `mapfile`, `sld`, `qgis`/`qml`, `ol-flat`. Targets: `mapbox`, `sld`, `qgis`/`qml`. ([geostyler-cli](https://github.com/geostyler/geostyler-cli), [DeepWiki on QGIS/QML](https://deepwiki.com/geostyler/geostyler-cli/4.2-qgisqml-format))

### When vector tiles work — and when they don't

**Works:** simple `SimpleMarker`/`SimpleLine`/`SimpleFill`, categorized/graduated on numeric or string fields, basic rule-based filters, scale-dependent visibility, basic label expressions (concat of fields).

**Breaks / needs fallback to WMS:**

| QGIS feature | Status with geostyler |
|---|---|
| `LinePatternFill` (hatched fill) | Not representable in MapLibre — needs WMS |
| Base64-embedded `SvgMarker` | QML stores SVG inline; MapLibre needs a sprite atlas at a URL — needs preprocessing or WMS fallback |
| `RenderMetersInMapUnits` (size in metres) | MapLibre sizes in pixels only — needs zoom-interpolated approximation or WMS |
| Multi-rule data-defined symbols (per-feature expression-driven symbol) | Only flat rules survive — needs simplification or WMS |
| QGIS expression syntax (`@map_scale`, `array_*`, geometry functions) | Only a subset maps to MapLibre expressions |
| Diagram/Cluster/HeatmapRenderer | Not supported — needs WMS |
| Inverted polygon fill / shapeburst | Not supported — needs WMS |

**Indexer rule:** mark a layer "vector-tile-eligible" if the QML root renderer is `singleSymbol|categorizedSymbol|graduatedSymbol|RuleRenderer` AND all symbol layers ∈ `{SimpleMarker, SimpleLine, SimpleFill, SimpleFillSymbolLayerV2}` AND no `field_RenderMetersInMapUnits=1`. Otherwise fall back to WMS via py-qgis-server.

[bridgestyle](https://pypi.org/project/bridgestyle/) (Python, MIT) sometimes handles cases geostyler-cli misses (especially label expressions) — keep it as a second-pass converter.

---

## 4. Authentik + Traefik forward-auth

### Outpost choice: **embedded outpost**

Authentik ships an embedded outpost by default (runs inside the main Authentik container, listens on `:9000`). Use this unless you need to terminate auth in a separate failure domain. Standalone proxy outposts are needed only when the upstream is in a different network namespace from Authentik. ([Authentik docs](https://docs.goauthentik.io/add-secure-apps/providers/proxy/server_traefik/), [Coolify guide](https://coolify.io/docs/knowledge-base/proxy/traefik/protect-services-with-authentik))

In Authentik admin:
1. Create a **Provider** of type "Proxy" → mode "Forward auth (single application)" → external host = `https://webgis.planportal.de`.
2. Create an **Application** linked to that provider.
3. Bind groups (e.g. `cuxhaven-editors`, `frankfurt-readers`) to the application via Policy bindings.

### Traefik dynamic middleware (verbatim from docs)

```yaml
# /traefik/dynamic/authentik.yaml
http:
  middlewares:
    authentik-auth:
      forwardAuth:
        address: 'http://authentik-server:9000/outpost.goauthentik.io/auth/traefik'
        trustForwardHeader: true
        authResponseHeaders:
          - X-authentik-username
          - X-authentik-groups
          - X-authentik-entitlements
          - X-authentik-email
          - X-authentik-name
          - X-authentik-uid
          - X-authentik-jwt
          - X-authentik-meta-jwks
          - X-authentik-meta-outpost
          - X-authentik-meta-provider
          - X-authentik-meta-app
          - X-authentik-meta-version
```

Apply as a Docker label:

```yaml
labels:
  - "traefik.http.routers.planportal.middlewares=authentik-auth@file"
```

### Per-project gating

Two approaches, both production-proven:

1. **One Authentik application per project** — bind project-specific groups. Router rule: `Host(\`webgis.planportal.de\`) && Path(\`/p/cuxhaven\`) -> authentik-cuxhaven@file`. Verbose but the cleanest audit trail.

2. **One Authentik application + header-based gating** — single `authentik-auth` middleware adds `X-Authentik-Groups`; a tiny reverse-proxy sidecar (or a Traefik plugin like `traefik-jwt-plugin`) inspects the header and 403s if the requested project is not in groups. Cheaper to maintain.

We recommend **#1 for ≤20 projects, #2 above that.**

### POLAR receives user/group from headers

POLAR is a static SPA — Traefik adds the headers on **page load**, then the SPA needs a way to read them. Two patterns:

1. **`/whoami` endpoint** behind the same middleware that echoes `X-Authentik-Username/-Groups` as JSON. The SPA fetches `/whoami` after load.

2. **Cookie-injected metadata** via Traefik response-headers middleware that copies `X-Authentik-Groups` into a cookie readable by JS.

Sample whoami sidecar (10 lines of Go or Python Flask):

```python
from flask import Flask, request, jsonify
app = Flask(__name__)
@app.get('/whoami')
def whoami():
    return jsonify(
        user=request.headers.get('X-Authentik-Username'),
        email=request.headers.get('X-Authentik-Email'),
        groups=(request.headers.get('X-Authentik-Groups') or '').split('|'),
    )
```

In POLAR, fetch on init and stash in a tiny store module so plugins can read it (e.g. an "AdminBadge" plugin only renders for the `planportal-admin` group).

---

## 5. Indexer service architecture

Goal: a long-running Python service that watches `/srv/gis/<project>/`, parses `.qgs`/`.qgz`/QField-zip, syncs metadata to Postgres, emits `services.json` for POLAR, validates `GetCapabilities` against py-qgis-server, and kicks off vector-tile bakes.

### High-level flow

```
inotify event
   │
   ▼
discover_changes()  ──► classify(.qgs | .qgz | QField-zip)
   │
   ▼
parse_qgs_xml()  ──► {layers, themes, extents, crs, layouts}
   │
   ▼
verify_against_pyqgis()  ──► GET /qgisserver/?MAP=...&REQUEST=GetCapabilities
   │
   ▼
write_to_postgres()  ──► table planportal.project (jsonb metadata)
   │
   ▼
emit_services_json()  ──► /srv/web/services.json (POLAR consumes)
   │
   ▼
queue_vector_bake()  ──► celery → tippecanoe + geostyler-cli
```

### Pseudo-code

```python
# indexer/main.py
import asyncio, hashlib, json, zipfile, base64
import xml.etree.ElementTree as ET
from pathlib import Path
import httpx, asyncpg
from watchfiles import awatch

QGS_ROOT = Path('/srv/gis')
SERVICES_JSON = Path('/srv/web/services.json')
PYQGIS = 'http://qgisserver:8080'

async def parse_qgs(qgs_path: Path) -> dict:
    """Parse a .qgs (or .qgs inside .qgz) into project metadata."""
    if qgs_path.suffix == '.qgz':
        with zipfile.ZipFile(qgs_path) as z:
            inner = next(n for n in z.namelist() if n.endswith('.qgs'))
            tree = ET.parse(z.open(inner))
    else:
        tree = ET.parse(qgs_path)
    root = tree.getroot()
    proj_crs = root.find('.//projectCrs/spatialrefsys/authid').text
    extent = root.find('.//ProjectViewSettings/Extent')
    bbox = [float(extent.find(t).text) for t in ('xmin','ymin','xmax','ymax')]

    layers = []
    for ml in root.findall('.//projectlayers/maplayer'):
        layers.append({
            'id': ml.findtext('id'),
            'name': ml.findtext('layername'),
            'datasource': ml.findtext('datasource'),
            'crs': ml.findtext('.//srs/spatialrefsys/authid'),
            'type': ml.get('type'),   # vector / raster
            'wms': ml.findtext('flags/Identifiable') == '1',
        })

    themes = []                       # <visibility-presets> in QGIS XML
    for preset in root.findall('.//visibility-presets/visibility-preset'):
        themes.append({
            'name': preset.get('name'),
            'visible_layers': [l.get('id') for l in preset.findall('layer') if l.get('visible')=='1'],
        })

    layouts = [l.get('name') for l in root.findall('.//Layout')]

    return {
        'crs': proj_crs, 'bbox': bbox,
        'layers': layers, 'themes': themes, 'print_layouts': layouts,
    }

async def verify_capabilities(project_slug: str) -> bool:
    url = f'{PYQGIS}/?MAP={project_slug}&SERVICE=WMS&REQUEST=GetCapabilities'
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url)
        return r.status_code == 200 and b'<WMS_Capabilities' in r.content

def emit_services_json(projects: list[dict]) -> None:
    """POLAR's rawLayerList.initializeLayerList expects this shape."""
    services = []
    for p in projects:
        for layer in p['layers']:
            services.append({
                'id': f"{p['slug']}__{layer['id']}",
                'name': layer['name'],
                'typ': 'WMS' if layer['wms'] else 'WFS',
                'url': f"https://webgis.planportal.de/qgisserver/?MAP={p['slug']}",
                'layers': layer['id'],
                'format': 'image/png',
                'version': '1.3.0',
                'crs': layer['crs'],
            })
    SERVICES_JSON.write_text(json.dumps(services, indent=2))

async def handle_qfield_zip(zip_path: Path) -> dict:
    """LL-WIE-style self-contained: shp + base64-encoded QML inside zip."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        qgs   = next((n for n in names if n.endswith('.qgs')), None)
        shps  = [n for n in names if n.endswith('.shp')]
        # Some packagers embed the QML as base64 in a sidecar JSON
        sidecar = next((n for n in names if n.endswith('.styles.json')), None)
        if sidecar:
            data = json.loads(z.read(sidecar))
            for layer_id, b64 in data.items():
                qml_bytes = base64.b64decode(b64)
                # write to disk so QGIS Server can find it next to the .shp
                outdir = QGS_ROOT / zip_path.stem / 'styles'
                outdir.mkdir(parents=True, exist_ok=True)
                (outdir / f'{layer_id}.qml').write_bytes(qml_bytes)
        # Extract everything into /srv/gis/<slug>/
        z.extractall(QGS_ROOT / zip_path.stem)
    return await parse_qgs(QGS_ROOT / zip_path.stem / Path(qgs).name)

def is_vector_tile_eligible(layer: dict, qml_path: Path) -> bool:
    if layer['type'] != 'vector':
        return False
    qml = ET.parse(qml_path).getroot()
    renderer = qml.find('.//renderer-v2')
    rtype = renderer.get('type') if renderer is not None else None
    if rtype not in {'singleSymbol','categorizedSymbol','graduatedSymbol','RuleRenderer'}:
        return False
    allowed = {'SimpleMarker','SimpleLine','SimpleFill','SimpleFillSymbolLayerV2'}
    for sl in qml.findall('.//symbol/layer'):
        if sl.get('class') not in allowed:
            return False
        if any(p.get('k')=='RenderMetersInMapUnits' and p.get('v')=='1'
               for p in sl.findall('Option/Option')):
            return False
    return True

async def queue_bake(slug: str, layer: dict, qml_path: Path):
    # Convert QML → MapLibre style.json
    style_path = Path(f'/srv/tiles/{slug}/{layer["id"]}.style.json')
    await asyncio.create_subprocess_exec(
        'geostyler-cli', '-s','qml','-t','mapbox',
        '-o', str(style_path), str(qml_path),
    )
    # tippecanoe: ogr2ogr → GeoJSON → PMTiles
    geojson = f'/tmp/{layer["id"]}.geojson'
    await asyncio.create_subprocess_exec(
        'ogr2ogr', '-f','GeoJSON','-t_srs','EPSG:4326',
        geojson, layer['datasource'],
    )
    await asyncio.create_subprocess_exec(
        'tippecanoe', '-o', f'/srv/tiles/{slug}/{layer["id"]}.pmtiles',
        '--layer', layer['id'], '--maximum-zoom=14', '--drop-densest-as-needed',
        '--force', geojson,
    )

async def main():
    pool = await asyncpg.create_pool(dsn=...)
    async for changes in awatch(str(QGS_ROOT)):
        # debounce: collect 2 s of changes
        await asyncio.sleep(2)
        projects = []
        for change, path in changes:
            p = Path(path)
            if p.suffix in {'.qgs', '.qgz'}:
                meta = await parse_qgs(p)
            elif p.suffix == '.zip':
                meta = await handle_qfield_zip(p)
            else:
                continue
            meta['slug'] = p.parent.name
            if not await verify_capabilities(meta['slug']):
                continue
            async with pool.acquire() as c:
                await c.execute("""
                  INSERT INTO planportal.project(slug, metadata, updated_at)
                  VALUES($1, $2, now())
                  ON CONFLICT(slug) DO UPDATE SET metadata=$2, updated_at=now()
                """, meta['slug'], json.dumps(meta))
            for layer in meta['layers']:
                qml = p.parent / 'styles' / f"{layer['id']}.qml"
                if qml.exists() and is_vector_tile_eligible(layer, qml):
                    asyncio.create_task(queue_bake(meta['slug'], layer, qml))
            projects.append(meta)
        emit_services_json(projects)
```

### Why parse XML rather than use PyQGIS?

PyQGIS gives correct semantics but pulls a ~1 GB QGIS container. For the indexer, `xml.etree.ElementTree` on a `.qgs` file gets ≥95 % of the metadata (layer tree, `<visibility-presets>` = map themes, `<ProjectCrs>`, `<Extent>`, `<Layout>`) without the dependency. Run a **separate** PyQGIS-backed validator container only as a periodic batch check.

---

## 6. Gotchas & pitfalls (2026 community wisdom)

### POLAR
- **masterportalAPI does not follow SemVer.** Pin exactly (`2.48.0`). Each bump = full QA across every plugin. POLAR upstream documents this in `arcana.md`.
- **OpenLayers 10+ arrow-key swallowing**: any custom plugin with focused inputs (especially `v-radio`, but also `v-text-field` inside Vuetify dialogs) must `@keydown.up.stop`/down/left/right or the map pans while the user types.
- **Plugin store namespacing**: integration between plugins uses literal action paths like `'plugin/loadingIndicator/addLoadingKey'` — typos fail silently. Centralise the strings in a `constants.ts`.
- **Vue 2 lock-in**: POLAR is on Vue 2.7. Migration to Vue 3 is *not* on the public roadmap. Plan a 5-year horizon, then re-evaluate.
- **No first-class TypeScript types for plugin options** — `@polar/lib-custom-types` is incomplete. Expect to write your own option interfaces.

### py-qgis-server
- **Workers leak on QGIS rendering crashes.** Always set `QGSRV_SERVER_MEMORY_HIGH_WATER_MARK=0.85` so workers auto-recycle.
- **`STRICT_CHECK=yes` is brutal on large projects.** Disable in prod, run a nightly validation pass instead.
- **GetCapabilities behind reverse-proxy** *will* return `localhost:8080` URLs if you forget `QGSRV_SERVER_PROXY_URL`. POLAR/QGIS Desktop then can't load layers.
- **Custom CRS is per-`$HOME`** — Authority codes from `srs.db` only resolve if the file is in `$HOME/QGIS/QGIS3/profiles/default/resources/srs.db`. Mount `qgis-home` as a named volume.
- **Font fallback warnings flood logs** — every project with a missing font logs ~20 warnings on every render. `fc-cache -fv` at image build time + `find /srv/gis -name '*.qgs' | xargs grep -lE 'font="[^"]+"'` for an audit list.
- **Deprecation notice**: 3liz is steering users to **QJazz** ([github.com/3liz/qjazz](https://github.com/3liz/qjazz)). py-qgis-server 1.9.x is maintained but not getting new features. Worth a feasibility spike for Q3 2026.

### martin + PMTiles
- **No native auth.** PMTiles bypassing Martin is a DoS / egress-cost risk per upstream. Force all PMTiles traffic through Martin and put Authentik in front.
- **PMTiles hot-reload is NOT implemented** (issue [maplibre/martin#2180](https://github.com/maplibre/martin/issues/2180)). MBTiles directories are watched, PMTiles requires a Martin restart. Workaround: write to `*.pmtiles.new`, then atomic rename, then `docker kill -s HUP` Martin.
- **`auto_publish` exposes everything** in a PG schema. For Planportal, **explicitly list tables** under `postgres.tables:` — auto-publish leaks dev-only tables to prod.
- **EPSG:25832 in PMTiles**: tippecanoe only emits **EPSG:3857** vector tiles. Reproject in `ogr2ogr -t_srs EPSG:4326` first; MapLibre will reproject the display.

### geostyler-cli / QML → MapLibre
- **Conversion is silently lossy.** Always diff a server-rendered WMS image against a vector-tile rendered MapLibre image before declaring a layer "vector-eligible". For multi-rule QML, geostyler often drops rules past the first.
- **Base64-embedded SVG markers** in QML must be extracted, written as files, uploaded as a sprite atlas, and referenced in the style — geostyler-cli does **not** do this automatically.
- **Label expressions** mapping is best-effort; QGIS `concat()` works, but `format_number()`, `to_real()`, geometry functions don't translate.

### Authentik + Traefik
- **`trustForwardHeader: true` is mandatory** — without it the outpost can't see the original client URL and login redirects loop.
- **Auth header stripping**: by default the `Authorization` header is consumed by Authentik (community thread [traefik#22365](https://community.traefik.io/t/authorisation-header-missing-error-when-authentik-forwardauth-middleware-is-used/22365)). If you need it downstream (e.g. for a tile cache that uses bearer tokens), add it to `authResponseHeaders`.
- **Embedded outpost = single point of failure.** For >99.9 % SLA, deploy a second standalone outpost behind the same Traefik service.
- **Group string format** in `X-authentik-Groups` is **pipe-separated** (`group1|group2`), not comma. Splitting on `,` is the most common bug.

### Indexer
- **`watchfiles` over NFS is unreliable.** If `/srv/gis` is networked, fall back to polling every 60 s.
- **QField .zip can ship without a `.qgs`** (data-only sync packages). Skip cleanly rather than 500.
- **Concurrent edits**: a partial `.qgs` write looks like XML to the parser and errors out. Always look for a `.qgs~` lock file or wait 2 s after the last event.
- **Big projects (>2000 layers)**: parsing an 80 MB `.qgs` with `ElementTree` blocks the event loop for 5–10 s. Run parsing in a `ProcessPoolExecutor`.

---

## Open questions for user

1. **POLAR client SLA.** Are we OK staying on Vue 2 / masterportalAPI 2.48 for the next 3 years, or do we plan a migration to MasterPortal v3 proper (Vue 3) at some point?
2. **Vector-tile fallback policy.** When a QML can't translate cleanly, do we (a) fall back to WMS automatically, (b) flag the project as "needs styling rework", or (c) attempt a "best-effort" MapLibre style and accept visual drift?
3. **Per-project auth granularity.** One Authentik application per project (clean, verbose) or single application + header-based group gate (cheap, more code in our sidecar)?
4. **QJazz migration timeline.** 3liz is steering away from py-qgis-server toward QJazz. Should we plan a 6-month migration spike in 2026 H2, or pin on py-qgis-server 1.9.x for the next 18 months?
5. **PMTiles distribution.** Local files on the app server, or S3-compatible (MinIO/R2/Hetzner) with CDN in front? Affects both performance and the indexer's bake step.
6. **GetPrint UX.** Custom POLAR plugin that calls `qgisserver?REQUEST=GetPrint` (we sketched one), or pull in MapFish-Print as a separate microservice for richer layouts?
7. **Custom CRS bundle.** Cuxhaven uses EPSG:25832, Frankfurt sometimes uses Gauß-Krüger (EPSG:31466/7). Should the indexer auto-detect and inject `srs.db` overrides, or do we ship a curated `srs.db` in the image?
8. **Comment threads plugin** (mentioned in the prompt) — backed by what? A new Postgres table, or external (e.g. existing Beteiligung app reuse)?

---

### Sources

- POLAR — [README](https://github.com/Dataport/polar), [gettingStarted.md](https://github.com/Dataport/polar/blob/main/gettingStarted.md), [arcana.md](https://github.com/Dataport/polar/blob/main/arcana.md), [docs site](https://dataport.github.io/polar/)
- masterportalAPI — [npm](https://www.npmjs.com/package/@masterportal/masterportalapi) (2.58.0 current; POLAR pinned at 2.48.0)
- py-qgis-server — [docs](https://docs.3liz.org/py-qgis-server/), [configuration](https://docs.3liz.org/py-qgis-server/configuration.html), [schemes](https://docs.3liz.org/py-qgis-server/schemes.html), [cache](https://docs.3liz.org/py-qgis-server/cache.html), [intro](https://docs.3liz.org/py-qgis-server/intro.html), [repo](https://github.com/3liz/py-qgis-server), [entrypoint](https://github.com/3liz/py-qgis-server/blob/master/docker/docker-entrypoint.sh), [deprecation note](https://github.com/3liz/py-qgis-server/blob/master/DEPRECATION_NOTICE.md), [QJazz successor](https://github.com/3liz/qjazz)
- Martin — [docs](https://maplibre.org/martin/), [config-file](https://github.com/maplibre/martin/blob/main/docs/content/config-file/index.md), [sources-files (PMTiles)](https://github.com/maplibre/martin/blob/main/docs/content/sources-files.md), [run-with-docker](https://github.com/maplibre/martin/blob/main/docs/content/run-with-docker.md)
- geostyler-cli — [repo](https://github.com/geostyler/geostyler-cli), [QGIS/QML format DeepWiki](https://deepwiki.com/geostyler/geostyler-cli/4.2-qgisqml-format), [geostyler-qgis-parser](https://github.com/geostyler/geostyler-qgis-parser), [bridgestyle alternative](https://pypi.org/project/bridgestyle/)
- tippecanoe — [felt/tippecanoe](https://github.com/felt/tippecanoe), [PMTiles creation guide](https://docs.protomaps.com/pmtiles/create)
- Authentik forward-auth — [docs](https://docs.goauthentik.io/add-secure-apps/providers/proxy/server_traefik/), [Coolify guide](https://coolify.io/docs/knowledge-base/proxy/traefik/protect-services-with-authentik), [Traefik forum: Authorization header stripping](https://community.traefik.io/t/authorisation-header-missing-error-when-authentik-forwardauth-middleware-is-used/22365)
- QGIS XML / map themes / QField packaging — [QgsMapThemeCollection](https://qgis.org/pyqgis/master/core/QgsMapThemeCollection.html), [QField packaging docs](https://docs.qfield.org/reference/qfieldcloud/projects/), [QGIS file formats appendix](https://docs.qgis.org/3.44/en/docs/user_manual/appendices/qgis_file_formats.html)
- Real-world POLAR/MasterPortal examples — [Berlin Umweltatlas](https://github.com/technologiestiftung/umweltatlas-masterportal-v3), [terrestris masterportal-addons](https://github.com/terrestris/masterportal-addons)
