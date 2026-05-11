"""Indexer entry point.

Cold-start sequence:
  1. Seed: copy any zips from /srv/seed → /srv/gis (one-shot on first boot).
  2. Initial scan: walk /srv/gis, parse every .qgs/.qgz, write to DB, emit services.json.
  3. Watch loop: react to filesystem changes with a 2-second debounce.
  4. QFC sync loop: poll QFieldCloud every 15 min (if configured).
"""
from __future__ import annotations

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import structlog
from watchfiles import awatch

from . import bake, caps_verify, config, db, qfc_sync, services_emit
from .eligibility import is_vector_tile_eligible
from .qgs_parse import ProjectMeta, parse_qgs
from .zip_to_qgs import extract_qfield_zip


def _setup_logging() -> None:
    logging.basicConfig(level=config.LOG_LEVEL, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )


log = structlog.get_logger("indexer")


async def _seed_from_dir() -> None:
    if not config.SEED_DIR.exists():
        return
    for zip_path in config.SEED_DIR.glob("*.zip"):
        slug = zip_path.stem
        if (config.QGS_ROOT / slug).exists():
            continue
        log.info("seed extract", zip=zip_path.name, slug=slug)
        extract_qfield_zip(zip_path, config.QGS_ROOT)
    for qgs_path in config.SEED_DIR.glob("*.qgs"):
        target = config.QGS_ROOT / qgs_path.stem / qgs_path.name
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(qgs_path, target)
        log.info("seed copy", file=qgs_path.name)


def _find_project_qgs(slug_dir: Path) -> Path | None:
    """Return the canonical .qgs/.qgz for a slug dir.

    Preference order:
      1. <slug>/<slug>.qgz   (production: zipped, single file)
      2. <slug>/<slug>.qgs   (unzipped variant)
      3. first .qgs in the tree
      4. first .qgz in the tree
    """
    for candidate in (slug_dir / f"{slug_dir.name}.qgz", slug_dir / f"{slug_dir.name}.qgs"):
        if candidate.exists():
            return candidate
    return next(slug_dir.rglob("*.qgs"), None) or next(slug_dir.rglob("*.qgz"), None)


async def _ingest_slug(slug: str) -> ProjectMeta | None:
    """Parse + DB upsert. Capabilities verification + vector bakes run
    in the background so the indexer never blocks initial scan on
    py-qgis-server's slow first-load of large QGIS projects.
    """
    slug_dir = config.QGS_ROOT / slug
    qgs = _find_project_qgs(slug_dir)
    if qgs is None:
        log.warning("no .qgs found", slug=slug)
        return None

    try:
        meta = parse_qgs(qgs, slug=slug)
    except Exception as e:  # noqa: BLE001
        log.error("parse failed", slug=slug, error=str(e))
        await db.record_event(slug, "parse_failed", {"error": str(e)})
        return None

    await db.upsert_project(
        meta,
        qgs_path=str(qgs),
        qgs_mtime=datetime.fromtimestamp(qgs.stat().st_mtime, tz=timezone.utc),
        status="active",
    )
    log.info(
        "ingested",
        slug=slug,
        layers=len(meta.layers),
        themes=len(meta.themes),
        bbox=bool(meta.bbox),
    )

    # Background tasks — don't block the initial scan.
    asyncio.create_task(_verify_in_background(meta, qgs))
    asyncio.create_task(_bake_eligible(meta))
    return meta


async def _verify_in_background(meta: ProjectMeta, qgs: "Path") -> None:
    ok, err = await caps_verify.verify(meta.slug)
    if not ok:
        log.warning("caps verify failed", slug=meta.slug, error=err[:200])
        await db.record_event(meta.slug, "caps_failed", {"error": err[:200]})
        await db.upsert_project(
            meta,
            qgs_path=str(qgs),
            qgs_mtime=datetime.fromtimestamp(qgs.stat().st_mtime, tz=timezone.utc),
            status="error",
        )
    else:
        log.info("caps verify ok", slug=meta.slug)


async def _bake_eligible(meta: ProjectMeta) -> None:
    slug_dir = config.QGS_ROOT / meta.slug
    for layer in meta.layers:
        qml = slug_dir / "styles" / f"{layer.id}.qml"
        if not qml.exists():
            qml = slug_dir / f"{layer.id}.qml"
        eligible, reason = is_vector_tile_eligible(layer.layer_type, qml if qml.exists() else None)
        if not eligible:
            log.debug("skip bake", slug=meta.slug, layer=layer.id, reason=reason)
            continue
        if not layer.datasource:
            continue
        result = await bake.bake_layer(
            meta.slug, layer.id, layer.datasource, qml if qml.exists() else None
        )
        log.info(
            "baked",
            slug=meta.slug,
            layer=layer.id,
            pmtiles=bool(result.get("pmtiles_path")),
            warnings=result.get("warnings"),
        )


async def _initial_scan() -> list[ProjectMeta]:
    metas: list[ProjectMeta] = []
    if not config.QGS_ROOT.exists():
        config.QGS_ROOT.mkdir(parents=True)
        return metas
    for entry in config.QGS_ROOT.iterdir():
        if not entry.is_dir():
            continue
        meta = await _ingest_slug(entry.name)
        if meta:
            metas.append(meta)
    return metas


def _affected_slugs(changes) -> set[str]:
    slugs: set[str] = set()
    for _change, path in changes:
        p = Path(path)
        # Find the path component immediately under QGS_ROOT.
        try:
            rel = p.relative_to(config.QGS_ROOT)
        except ValueError:
            continue
        parts = rel.parts
        if not parts:
            continue
        slugs.add(parts[0])
    return slugs


async def _watch_loop() -> None:
    log.info("watching", path=str(config.QGS_ROOT))
    async for changes in awatch(
        str(config.QGS_ROOT),
        debounce=int(config.DEBOUNCE_SECONDS * 1000),
        step=200,
    ):
        slugs = _affected_slugs(changes)
        if not slugs:
            continue
        log.info("changes", slugs=sorted(slugs))
        metas: list[ProjectMeta] = []
        for slug in sorted(slugs):
            slug_dir = config.QGS_ROOT / slug
            if not slug_dir.exists():
                # Project removed.
                continue
            meta = await _ingest_slug(slug)
            if meta:
                metas.append(meta)
        # Re-emit services.json reflecting current DB state.
        full = await _initial_scan()
        services_emit.emit(full)


async def main() -> None:
    _setup_logging()
    log.info("indexer starting", qgs_root=str(config.QGS_ROOT))
    await db.init_pool()
    await _seed_from_dir()
    metas = await _initial_scan()
    services_emit.emit(metas)
    log.info("initial scan done", projects=len(metas))

    tasks = [asyncio.create_task(_watch_loop())]
    if config.QFC_BASE_URL and config.QFC_ADMIN_TOKEN:
        tasks.append(asyncio.create_task(qfc_sync.sync_loop()))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
