# projects/

Drop QGIS projects here as **directories** containing a `<slug>.qgs` or
`<slug>.qgz`, plus their supporting data (relative paths only). Indexer
picks them up on next file-system event.

## Self-contained zips

You can also drop a zip named `<slug>.zip`. On boot the indexer extracts
it to `/srv/gis/<slug>/` and (if no `.qgs` is inside) synthesises a stub
project referencing every `.shp` found.

### Special case: LL-WIE-2427 packaging

The Wiesbaden Spielplätze project ships as a self-contained zip with:

- One or more `.shp` layers
- A sidecar `<slug>.styles.json` mapping `layer_id → base64(QML)`

The indexer decodes those QML blobs into `styles/<layer_id>.qml` next to
the layers — QGIS Server's standard `<layer>.qml` discovery picks them
up automatically.

## What does NOT belong here

- `.gpkg` files larger than 50 MB → store under `/srv/gis/<slug>/` on
  the host (gitignored from this directory; sync via QFC or rsync).
- Raster tiffs → host-side; `.qgs` references via `file:///` URI.
- Anything containing credentials.

See `.gitignore` for the full exclusion list.
