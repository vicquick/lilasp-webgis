"""Postgres writes — project, layer, theme, layout upserts."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from . import config
from .qgs_parse import ProjectMeta


_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=config.DATABASE_URL, min_size=1, max_size=4)
    return _pool


@asynccontextmanager
async def conn() -> AsyncIterator[asyncpg.Connection]:
    pool = await init_pool()
    async with pool.acquire() as c:
        yield c


def _bbox_wkt(meta: ProjectMeta) -> str | None:
    """Project BBOX → POLYGON WKT in EPSG:4326. We don't reproject here; the
    DB column declares 4326 but stores whatever we hand it. The web layer
    reprojects for display when needed.
    """
    if not meta.bbox:
        return None
    xmin, ymin, xmax, ymax = meta.bbox
    return f"POLYGON(({xmin} {ymin}, {xmax} {ymin}, {xmax} {ymax}, {xmin} {ymax}, {xmin} {ymin}))"


async def upsert_project(meta: ProjectMeta, qgs_path: str, qgs_mtime, status: str = "active") -> None:
    async with conn() as c:
        bbox = _bbox_wkt(meta)
        await c.execute(
            """
            INSERT INTO planportal.project
                (slug, title, qgs_path, qgs_mtime, crs, bbox, status, metadata, updated_at)
            VALUES ($1, $2, $3, $4, $5, ST_GeomFromText($6, 4326), $7, $8::jsonb, now())
            ON CONFLICT (slug) DO UPDATE SET
                title = EXCLUDED.title,
                qgs_path = EXCLUDED.qgs_path,
                qgs_mtime = EXCLUDED.qgs_mtime,
                crs = EXCLUDED.crs,
                bbox = EXCLUDED.bbox,
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            """,
            meta.slug,
            meta.title,
            qgs_path,
            qgs_mtime,
            meta.crs,
            bbox,
            status,
            json.dumps({"print_layouts": meta.print_layouts}),
        )

        await c.execute(
            "DELETE FROM planportal.project_layer WHERE project_slug = $1", meta.slug
        )
        if meta.layers:
            await c.executemany(
                """
                INSERT INTO planportal.project_layer
                    (project_slug, layer_id, name, layer_type, geom_type,
                     datasource, crs, wms_visible)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                [
                    (
                        meta.slug,
                        l.id,
                        l.name,
                        l.layer_type,
                        l.geom_type,
                        l.datasource,
                        l.crs,
                        l.wms_visible,
                    )
                    for l in meta.layers
                ],
            )

        await c.execute(
            "DELETE FROM planportal.project_theme WHERE project_slug = $1", meta.slug
        )
        if meta.themes:
            await c.executemany(
                """
                INSERT INTO planportal.project_theme
                    (project_slug, name, visible_layers)
                VALUES ($1, $2, $3::jsonb)
                """,
                [
                    (meta.slug, t.name, json.dumps(t.visible_layer_ids))
                    for t in meta.themes
                ],
            )


async def record_event(slug: str | None, kind: str, payload: dict | None = None) -> None:
    async with conn() as c:
        await c.execute(
            """
            INSERT INTO planportal.indexer_event (project_slug, kind, payload)
            VALUES ($1, $2, $3::jsonb)
            """,
            slug,
            kind,
            json.dumps(payload or {}),
        )
