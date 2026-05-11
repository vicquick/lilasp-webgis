# QGIS Server config

## `srs.db`

QGIS uses a SQLite `srs.db` per profile to resolve CRS authority codes.
The default ships with EPSG / IGNF / ESRI codes. We override it to ensure:

- EPSG:25832 (ETRS89 / UTM 32N) — Wiesbaden, Cuxhaven default
- EPSG:31466, 31467, 31468 (DHDN Gauß-Krüger Zonen 2/3/4) — Frankfurt legacy
- Cuxhaven-local Soldner Bessel (custom code, see `proj/cuxhaven-soldner.txt`)

To rebuild `srs.db` from a working QGIS Desktop profile:

```bash
cp ~/.local/share/QGIS/QGIS3/profiles/default/resources/srs.db ./srs.db
```

To verify after build:

```bash
docker run --rm -it planportal-qgisserver \
  sqlite3 /home/qgis/QGIS/QGIS3/profiles/default/resources/srs.db \
  "SELECT auth_name, auth_id, description FROM tbl_srs WHERE auth_id IN ('25832','31466','31467','31468');"
```

## Fonts

Bind-mount additional font directories at runtime:

```yaml
volumes:
  - /opt/lilasp-fonts:/usr/share/fonts/custom:ro
```

Run `fc-cache -fv` inside the container after adding fonts. Fontconfig
picks them up via the standard search path — no QGIS-specific config.

## Project caching

Configured via `QGSRV_*` env vars in `docker-compose.yml`. LRU is in-memory
per worker; restart a worker to flush its cache (or use the management API
at `:19876` if `QGSRV_MANAGEMENT_ENABLED=yes`).
