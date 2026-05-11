# ADR 0004 — Vector-tile eligibility rule

- Status: accepted
- Date: 2026-05-11

## Context

The previous QWC2 attempt tried to vector-tile every layer. MapLibre's
style spec can't express:

- `LinePatternFill` (hatched fill)
- Base64-embedded `SvgMarker`
- `RenderMetersInMapUnits` (size in metres)
- Multi-rule data-defined `CASE`
- `Diagram` / `Cluster` / `Heatmap` / inverted polygon / shapeburst
- A large subset of QGIS expression syntax (`@map_scale`, geometry funcs)

When `geostyler-cli` encounters these, it either silently drops rules or
emits a style that visually diverges from QGIS Desktop. The fidelity
contract breaks.

## Decision

Mark a layer **vector-tile-eligible** only if its QML renderer is in a
known-safe subset. Otherwise fall back to WMS via py-qgis-server.

Rule (implemented in `services/indexer/src/indexer/eligibility.py`):

1. Renderer ∈ `{singleSymbol, categorizedSymbol, graduatedSymbol, RuleRenderer}`
2. All symbol layers ∈ `{SimpleMarker, SimpleLine, SimpleFill, SimpleFillSymbolLayerV2}`
3. No `RenderMetersInMapUnits=1` property anywhere

Default to WMS for everything else. No best-effort drift.

## Consequences

- Pixel-identical rendering for non-trivial styles (the whole point).
- Lower vector-tile coverage than naive baseline. We are explicitly
  trading throughput for fidelity.
- The eligibility checker is one Python function — easy to evolve as we
  improve coverage of edge cases (e.g. by adopting bridgestyle for label
  expressions).
