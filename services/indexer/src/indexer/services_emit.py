"""Emit /srv/web/services.json — consumed by the SPA on boot.

Shape is tailored for our masterportalAPI-based client (see services/web/
src/lib/services-loader.ts). Each project gets one entry containing its
layer tree, themes, print layouts, and public URLs.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import config
from .qgs_parse import ProjectMeta


def _layer_dict(slug: str, layer) -> dict:
    """Per-layer record. Includes vector-tile URL if eligibility set."""
    return {
        "id": layer.id,
        "name": layer.name,
        "type": layer.layer_type,
        "geom_type": layer.geom_type,
        "crs": layer.crs,
        "wms_visible": layer.wms_visible,
        "wms_url": f"{config.PUBLIC_QGIS_BASE}/?MAP=file:/srv/gis/{slug}/{slug}.qgs",
        "wms_layer_name": layer.id,
        "wfs_url": f"{config.PUBLIC_QGIS_BASE}/?MAP=file:/srv/gis/{slug}/{slug}.qgs",
        # Indexer fills these after bake; default null.
        "pmtiles_url": None,
        "style_url": None,
    }


def _project_dict(p: ProjectMeta) -> dict:
    return {
        "slug": p.slug,
        "title": p.title,
        "crs": p.crs,
        "bbox": list(p.bbox) if p.bbox else None,
        "layers": [_layer_dict(p.slug, l) for l in p.layers],
        "themes": [
            {"name": t.name, "visible_layer_ids": t.visible_layer_ids}
            for t in p.themes
        ],
        "print_layouts": p.print_layouts,
        "endpoints": {
            "wms": f"{config.PUBLIC_QGIS_BASE}/?MAP=file:/srv/gis/{p.slug}/{p.slug}.qgs",
            "print": f"{config.PUBLIC_QGIS_BASE}/?MAP=file:/srv/gis/{p.slug}/{p.slug}.qgs",
        },
    }


def emit(projects: list[ProjectMeta], target: Path | None = None) -> Path:
    target = target or config.WEB_SERVICES_JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "projects": [_project_dict(p) for p in projects],
    }
    # Atomic write — the SPA fetches this on every page load.
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".services.", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        Path(tmp).replace(target)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target
