# ADR 0002 — py-qgis-server, not QJazz (yet)

- Status: accepted
- Date: 2026-05-11

## Context

3liz ships a deprecation notice in py-qgis-server pointing to QJazz as
the next-gen successor. QJazz is a complete rewrite (Rust-based proxy,
Python workers, gRPC dispatch). py-qgis-server 1.9.6 still receives
bugfixes.

## Decision

Use `3liz/qgis-map-server:1.9.6` (py-qgis-server) for Phase 0 and 1.
Plan a 6-month feasibility spike on QJazz starting H2 2026.

## Consequences

- We bet on a deprecated-but-still-maintained image for 18 months. Risk:
  bugfix tail goes quiet. Mitigation: pin the image SHA, audit upstream
  monthly.
- Our `services/qgis-server/Dockerfile` stays simple. Migration path is
  documented in `docs/adr/` once we spike QJazz.
