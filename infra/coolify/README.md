# Coolify deployment

Each `services/<name>/` is a standalone Coolify **Dockerfile application**.
Postgres and Redis are standalone Coolify resources.

## Per-service mapping

| Coolify resource | Source | Network |
|---|---|---|
| Standalone PostgreSQL 18 (+ PostGIS init.sql) | `infra/postgres/init.sql` | `planportal` |
| Standalone Redis 7 | — | `planportal` |
| `services/qgis-server` | `services/qgis-server/Dockerfile` | `planportal` |
| `services/martin` | image `ghcr.io/maplibre/martin:v0.18.0`, config mount | `planportal` |
| `services/indexer` | `services/indexer/Dockerfile` | `planportal` |
| `services/auth-gateway` | `services/auth-gateway/Dockerfile` | `planportal` |
| `services/web` | `services/web/Dockerfile` | `planportal` + `coolify` |

## Domains

| App | Domain | Routed under |
|---|---|---|
| web | `webgis.lilasp.de` | `/` |
| qgis-server | `webgis.lilasp.de` | `/qgisserver` (StripPrefix) |
| martin | `webgis.lilasp.de` | `/tiles` (StripPrefix) |
| auth-gateway | `webgis.lilasp.de` | `/whoami` |

All routes are middleware-gated by `authentik-auth@file` (see
`infra/traefik/dynamic/authentik.yaml`). Drop both YAML files into
`/data/coolify/proxy/dynamic/` and reload Traefik.

## Volumes

| Volume | Purpose | Owner |
|---|---|---|
| `planportal-gis-data` | `/srv/gis` — QGIS projects | indexer (rw), qgis-server (ro), martin (ro through tiles) |
| `planportal-tiles-data` | `/srv/tiles` — PMTiles + styles | indexer (rw), martin (ro) |
| `planportal-web-static` | `/srv/web` — `services.json` only | indexer (rw), web (ro) |
| `planportal-qgis-home` | `/home/qgis` profile (cache, custom CRS) | qgis-server |
| `planportal-postgres-data` | Postgres data | postgres |

## Migration from QWC2 stack

The old QWC2 app (`v88wco4g4kws8848wgsgk0k0`) shares the host directory
`/var/www/qgis-projects`. During the Phase 0 cutover, mount **read-only**
into the new indexer's `/srv/gis` while we validate parity. After cutover
(when `services.json` matches expectations), retire the old app.
