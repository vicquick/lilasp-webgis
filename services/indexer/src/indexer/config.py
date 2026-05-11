"""Runtime config from env. No magic; fail loud on missing required keys."""
from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"env var {key} is required")
    return val or ""


DATABASE_URL = _env("DATABASE_URL", required=True)
REDIS_URL = _env("REDIS_URL", "redis://redis:6379/0")
QGS_ROOT = Path(_env("QGS_ROOT", "/srv/gis"))
TILES_ROOT = Path(_env("TILES_ROOT", "/srv/tiles"))
WEB_SERVICES_JSON = Path(_env("WEB_SERVICES_JSON", "/srv/web/services.json"))
SEED_DIR = Path(_env("SEED_DIR", "/srv/seed"))

PYQGIS_URL = _env("PYQGIS_URL", "http://qgisserver:8080").rstrip("/")
PUBLIC_QGIS_BASE = _env("PUBLIC_QGIS_BASE", "/qgisserver")
PUBLIC_TILES_BASE = _env("PUBLIC_TILES_BASE", "/tiles")

DEBOUNCE_SECONDS = float(_env("INDEXER_DEBOUNCE_SECONDS", "2"))
PARSE_POOL_WORKERS = int(_env("INDEXER_PARSE_POOL", "2"))

QFC_BASE_URL = _env("QFC_BASE_URL", "")
QFC_ADMIN_TOKEN = _env("QFC_ADMIN_TOKEN", "")
QFC_SYNC_INTERVAL_MINUTES = int(_env("QFC_SYNC_INTERVAL_MINUTES", "15"))

LOG_LEVEL = _env("LOG_LEVEL", "INFO")
