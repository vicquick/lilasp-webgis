# ADR 0005 — Single public entry point, nginx reverse proxy

- Status: accepted
- Date: 2026-05-11

## Context

The earlier draft routed each service (`qgis-server`, `martin`,
`auth-gateway`, `web`) as its own Traefik router on
`webgis.lilasp.de/<prefix>`. That works but creates four public attack
surfaces and four places where the Authentik forward-auth middleware
must be applied correctly. A single misconfigured router silently
exposes a service.

## Decision

Only `planportal-web` carries Traefik labels. Its nginx reverse-proxies
`/qgisserver`, `/tiles`, `/whoami` to the internal containers across
the docker network. All other containers have **no Traefik labels** —
they are unreachable from the public internet.

## Consequences

Pros:
- One entry point, one Authentik middleware chain, one TLS cert.
- Internal containers cannot be hit even if a CDN, a Traefik label, or
  a DNS record leaks. Defence in depth.
- Rate-limiting and security headers applied once.
- `planportal-indexer`, `planportal-postgres`, `planportal-redis`
  literally cannot accept inbound HTTP from the internet.

Cons:
- Extra hop adds a few ms of latency to WMS / tile responses (mitigated
  by `proxy_buffering on`).
- nginx config carries proxy rules that *could* drift from the
  underlying container ports. Mitigation: container names + ports are
  pinned in `docker-compose.yml` and `infra/coolify/README.md`.
