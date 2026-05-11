# ADR 0006 — Coolify MCP destination_uuid limitation

- Status: accepted
- Date: 2026-05-11

## Context

The Coolify MCP wrapper's `service` and `database` create-action tools
don't expose `destination_uuid` (network) as a parameter. Coolify
requires it when the server has multiple destinations (it does — `ar`,
`bim-production`, `ml-production`, `reviewer-production`, `coolify`,
…). The wrapped Coolify HTTP API does accept it; the MCP layer just
hasn't surfaced it.

Result: cannot create new `standalone-postgresql`, `standalone-redis`,
or service-template resources through MCP without first picking an
existing destination via the UI.

## Decision

- Planportal runs as a single Coolify dockercompose application
  (`v88wco4g4kws8848wgsgk0k0`), which DOES accept `destination_uuid`
  via the `application` create-tool — though we inherited the existing
  app rather than creating a new one.
- Authentik deployment is a manual UI click ("Add new service →
  Authentik" in the Coolify dashboard). The compose we authored is in
  `infra/coolify/authentik-compose.yml` for reference, and the secrets
  are stashed in the deploy notes (rotated before commit).
- Long term: file an issue against the MCP wrapper to expose
  `destination_uuid` for `service` and `database` create actions, then
  migrate Authentik + per-service Planportal apps once that lands.

## Consequences

- Single-application deploy is faster than per-service Coolify apps,
  but loses some zero-downtime granularity (the whole compose restarts
  together).
- One Coolify resource means one set of env vars, one Traefik label
  surface, one git webhook trigger. Simpler operations now.
- We can break out into per-service apps later when the MCP supports
  it; the compose-internal structure already mirrors what those apps
  would look like.
