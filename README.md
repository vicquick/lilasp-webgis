# Planportal

WebGIS portal for `webgis.lilasp.de`. Fronts QGIS Server with a thin OpenLayers + masterportalAPI client. Pixel-identical to QGIS Desktop by construction — same renderer.

> **Status:** rebuild in progress (May 2026). Previous QWC2 stack archived at tag `archive/qwc2-2026-04-16`.

## Stack

| Layer | Component | Why |
|---|---|---|
| Reverse proxy | Traefik (Coolify) | TLS, forward-auth |
| Auth | Authentik (forward-auth) | SSO, group-gated projects |
| Auth sidecar | `auth-gateway` (Flask) | `/whoami` echoes Authentik headers to SPA |
| Map render | `py-qgis-server` (3liz 1.9.6) | WMS / WFS / GetPrint, same engine as desktop |
| Vector tiles | `martin` + PMTiles | Vector-eligible layers only (see ADR-0004) |
| Indexer | `indexer` (Python, asyncio + watchfiles) | Watches `/srv/gis/<project>/`, emits `services.json`, bakes tiles |
| Frontend | `web` (raw OpenLayers + `@masterportal/masterportalapi`) | Light, no Vue 2 lock-in |
| Metadata DB | PostgreSQL 18 + PostGIS | Project / layer / theme / role metadata |
| Cache | Redis | Tile + capabilities cache |
| QFC sync | `indexer.qfc_sync` (cron-driven) | Pulls `.qgs` / `.gpkg` from QFieldCloud every 15 min |

## Layout

```
docs/
  plan/        — vision + roadmap
  research/    — synthesised briefs (POLAR / py-qgis / martin / Authentik)
  adr/         — decision records
services/
  qgis-server/ — py-qgis-server image + fonts + custom CRS
  martin/      — vector tile server config
  indexer/     — Python: watch, parse, verify, emit, bake, qfc_sync
  auth-gateway/ — whoami sidecar
  web/         — OpenLayers + masterportalAPI client
infra/
  coolify/     — per-service Coolify hints
  traefik/     — dynamic forward-auth middleware
  postgres/    — schema init
projects/      — tracked .qgs / .qgz / project zips
scripts/       — bootstrap / restore helpers
```

## Quick start (local dev)

```bash
cp .env.example .env
docker compose up -d
# wait ~30s for indexer to ingest the demo project
open http://localhost:8080
```

The demo project (`LL-WIE-2427` — Wiesbaden Spielplätze) ships in `projects/` as a self-contained zip. The indexer extracts it on first boot.

## Production deploy

Each `services/<name>/` is a standalone Coolify Dockerfile app. DB and Redis are standalone Coolify resources. See `infra/coolify/README.md`.

## License

Internal. Predecessor (QWC2-based) was BSD-licensed via upstream `qwc2-demo-app`.
