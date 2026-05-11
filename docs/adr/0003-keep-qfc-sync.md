# ADR 0003 — Keep QFieldCloud sync (pragmatic), drop full mirror

- Status: accepted
- Date: 2026-05-11

## Context

Field workers edit in QField, sync back to QFieldCloud. Planportal needs
those edits visible. Three options were considered:

1. Drop QFC entirely. Edit only in QGIS Desktop, rsync `.qgs` up.
2. Keep the sync script only. Indexer's `qfc_sync` module pulls `.qgs`
   and supporting data from QFC every 15 min.
3. Full QFC mirror inside Planportal (deduped users, deduped roles,
   shared object storage). The previous-attempt ambition that killed
   momentum.

## Decision

Option 2 — keep the sync script.

The script (`services/indexer/src/indexer/qfc_sync.py`) is ~100 lines,
lifted from the QWC2-era `scripts/sync-qfc-projects.py`. Runs from the
indexer's main event loop. Idempotent.

## Consequences

- Field data lands in `/srv/gis/<slug>/` automatically.
- We avoid the user-mirror complexity and dependency on QFC internals.
- If QFC API breaks, sync stops but Planportal continues serving the
  last-known-good `.qgs` from disk.
