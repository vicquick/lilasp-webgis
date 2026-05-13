# projects/

**⛔ Never commit `.qgs` / `.qgz` to git.** QGIS embeds PostgreSQL
passwords in `datasource` strings — committing them to a public repo
leaks credentials. The whole directory is gitignored except this README.

Project files live on the Coolify volume `planportal-gis-data` mounted
at `/srv/gis` in the qgis-server + indexer containers. Populate it by:

1. **QFieldCloud sync** — the indexer's `qfc_sync` module pulls projects
   automatically every 15 min when `QFC_BASE_URL` + `QFC_ADMIN_TOKEN`
   env vars are set.
2. **Manual upload via SCP** — `scp -r <project>/ root@lilasp.de:/srv/gis-staging/<slug>/`,
   then on the host: `docker cp /srv/gis-staging/<slug>/. planportal-indexer:/srv/gis/<slug>/`.
3. **Direct mount** — for production we bind-mount `/srv/gis-staging/`
   on the host into `/srv/gis` in the container (see infra/coolify/).

## Expected layout

Each project is a directory containing a `<slug>.qgs` or `<slug>.qgz`
plus its supporting data with relative paths.

```
/srv/gis-staging/<slug>/
  ├── <slug>.qgz                    # or .qgs
  ├── data/                         # shapefiles, gpkg, etc.
  └── 260414/                       # SVG marker bundle dirs — names
      ├── Leuchtturm.svg            # match the relative paths inside
      └── Neuplanung2.svg           # the .qgs (<SvgFile><name>...).
```

## SVG markers / embedded symbols

QGIS resolves SVG paths inside a `.qgs` against:
1. The project file's own directory — drop SVG folders next to the
   `.qgz` and they're picked up automatically (preferred).
2. `QGIS_DEFAULT_SVG_PATHS` — we set this to `/srv/gis` so any SVG
   tree shared across projects can live at `/srv/gis/<shared>/...`.

If a theme renders without its custom point symbols, check the
qgisserver logs for `Could not load svg file` — that names exactly
which path is missing.

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
