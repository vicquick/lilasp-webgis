# ADR 0001 — Raw OpenLayers + masterportalAPI over a POLAR fork

- Status: accepted
- Date: 2026-05-11

## Context

POLAR (Dataport) is a Vue 2 + Vite 5 + Nx 22 monorepo wrapping
`@masterportal/masterportalapi`. Its plugin contract is clean (a
two-arg curried function dispatching to Vuex), but the framework brings
Vue 2 lock-in, the Nx monorepo structure, and pins masterportalAPI at
2.48.0 (upstream is 2.58.0).

## Decision

Skip POLAR. Consume `@masterportal/masterportalapi` directly. Build
our own thin plugin layer in `services/web/src/plugins/`.

## Consequences

Pros:
- No Vue 2 lock-in (we use vanilla TS + minimal DOM rendering).
- Free upgrade path on masterportalAPI without the Nx fork-management cost.
- Smaller surface — every plugin is ≤50 lines we own.

Cons:
- We reimplement Picker, LayerChooser, Gfi UIs from scratch (small —
  these are ~100 lines each given masterportalAPI does the heavy
  GetCapabilities / GetFeatureInfo work).
- We can't pull plugins from the POLAR ecosystem (their `addressSearch`,
  `pins`, `export` etc.) — re-evaluate at Phase 2 if we want any.

## Re-evaluate at

- Phase 2 milestone (after first project live in production).
- When masterportalAPI ships a breaking change we'd otherwise inherit
  from POLAR for free.
