"""Vector-tile bake pipeline: ogr2ogr → tippecanoe → PMTiles, plus QML → MapLibre style.

Best-effort. If geostyler-cli silently drops rules past the first, the
project owner is expected to either (a) flatten the QML in QGIS Desktop
or (b) leave the layer on the WMS path.
"""
from __future__ import annotations

import asyncio
import shlex
from pathlib import Path

import structlog

from . import config

log = structlog.get_logger(__name__)


async def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


async def bake_layer(slug: str, layer_id: str, datasource: str, qml_path: Path | None) -> dict:
    """Returns dict with `pmtiles_path`, `style_path`, and any `warnings`."""
    out_dir = config.TILES_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = out_dir / f"{layer_id}.geojson"
    pmtiles_path = out_dir / f"{layer_id}.pmtiles"
    style_path = out_dir / f"{layer_id}.style.json"
    warnings: list[str] = []

    # 1) ogr2ogr → GeoJSON in EPSG:4326 (tippecanoe input).
    code, _, err = await _run(
        [
            "ogr2ogr",
            "-f", "GeoJSON",
            "-t_srs", "EPSG:4326",
            "-skipfailures",
            str(geojson_path),
            datasource,
        ]
    )
    if code != 0:
        log.warning("ogr2ogr failed", slug=slug, layer=layer_id, stderr=err[:500])
        return {"pmtiles_path": None, "style_path": None, "warnings": [f"ogr2ogr: {err[:200]}"]}

    # 2) tippecanoe → PMTiles (atomic via .new + rename, since martin can't hot-reload).
    pmtiles_new = pmtiles_path.with_suffix(".pmtiles.new")
    code, _, err = await _run(
        [
            "tippecanoe",
            "-o", str(pmtiles_new),
            "--layer", layer_id,
            "--maximum-zoom=14",
            "--minimum-zoom=8",
            "--drop-densest-as-needed",
            "--force",
            str(geojson_path),
        ]
    )
    if code != 0:
        log.warning("tippecanoe failed", slug=slug, layer=layer_id, stderr=err[:500])
        pmtiles_new.unlink(missing_ok=True)
        return {"pmtiles_path": None, "style_path": None, "warnings": [f"tippecanoe: {err[:200]}"]}
    pmtiles_new.replace(pmtiles_path)

    # geostyler-cli (QML → MapLibre style) is intentionally NOT installed
    # in the indexer image — see Dockerfile. Vector tiles ship without a
    # custom style for now; WMS fallback covers high-fidelity rendering.
    # When geostyler-cli is added back, restore the subprocess call here.
    style_path = None
    if qml_path is None or not qml_path.exists():
        warnings.append("no QML alongside layer — martin default style")
    else:
        warnings.append("style baking deferred (geostyler-cli not installed)")

    # Drop the intermediate GeoJSON.
    geojson_path.unlink(missing_ok=True)

    return {
        "pmtiles_path": str(pmtiles_path),
        "style_path": str(style_path) if style_path else None,
        "warnings": warnings,
    }


def public_urls(slug: str, layer_id: str) -> tuple[str, str | None]:
    """Public URLs the SPA reads from services.json."""
    pm = f"{config.PUBLIC_TILES_BASE}/{slug}__{layer_id}/{{z}}/{{x}}/{{y}}"
    return pm, None
