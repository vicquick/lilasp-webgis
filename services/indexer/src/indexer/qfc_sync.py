"""QFieldCloud sync — pulls project files into /srv/gis/<slug>/.

Lifted from the QWC2-era `scripts/sync-qfc-projects.py` and adapted: no
QWC config-regen trigger (the indexer watcher reacts to file changes
directly via watchfiles).

Run periodically from the indexer's main loop. Idempotent.
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog

from . import config

log = structlog.get_logger(__name__)


# QFC project name → local slug (mirrors directory name under QGS_ROOT).
QFC_PROJECT_MAP: dict[str, str] = {
    "WIE_Spielplaetze":              "wiesbaden",
    "CUX_Spielplaetze":              "cuxhaven",
    "Cuxhaven_Spielplaetze":         "cuxhaven",
    "FFM_Naturerlebnisprofile":      "frankfurt_nep",
    "FFM_Orte":                      "frankfurt_orte",
    "FFM_Plaetze":                   "frankfurt_plaetze",
    "FFM_Wege":                      "frankfurt_wege",
    "FFM_FFEP":                      "frankfurt_ffep",
    "Schnelsen_HCS_Baeume":          "schnelsen_baeume",
}

_SKIP_SUFFIXES = (".qfs",)
_SKIP_NAMES = {"attachments.zip"}


@dataclass(slots=True)
class FileRec:
    name: str
    md5: str | None


async def _list_files(client: httpx.AsyncClient, project_id: str) -> list[FileRec]:
    r = await client.get(f"/files/{project_id}/")
    r.raise_for_status()
    return [FileRec(name=f["name"], md5=f.get("md5sum")) for f in r.json()]


async def _download(client: httpx.AsyncClient, project_id: str, name: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    async with client.stream("GET", f"/files/{project_id}/{name}/", follow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            async for chunk in r.aiter_bytes():
                f.write(chunk)
    tmp.replace(dest)


def _local_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 15), b""):
            h.update(chunk)
    return h.hexdigest()


async def sync_once() -> int:
    """One QFC sync pass. Returns the number of projects that changed."""
    if not config.QFC_BASE_URL or not config.QFC_ADMIN_TOKEN:
        log.info("QFC sync disabled — set QFC_BASE_URL + QFC_ADMIN_TOKEN to enable")
        return 0

    changed = 0
    async with httpx.AsyncClient(
        base_url=config.QFC_BASE_URL.rstrip("/"),
        headers={"Authorization": f"Token {config.QFC_ADMIN_TOKEN}"},
        timeout=httpx.Timeout(30.0, read=120.0),
    ) as client:
        r = await client.get("/projects/")
        r.raise_for_status()
        projects = r.json()

        for proj in projects:
            name = proj.get("name", "")
            slug = QFC_PROJECT_MAP.get(name)
            if not slug:
                continue
            project_id = proj.get("id")
            qgs_name = proj.get("project_filename")

            try:
                files = await _list_files(client, project_id)
            except httpx.HTTPError as e:
                log.warning("qfc list_files failed", project=name, error=str(e))
                continue

            wanted: list[FileRec] = []
            for f in files:
                low = f.name.lower()
                if low.endswith(_SKIP_SUFFIXES) or low in _SKIP_NAMES:
                    continue
                if low.endswith("_attachments.zip"):
                    continue
                wanted.append(f)

            dest_root = config.QGS_ROOT / slug
            project_changed = False
            for f in wanted:
                is_main = f.name == qgs_name
                local = dest_root / (
                    f"{slug}{Path(f.name).suffix}" if is_main else f.name
                )
                if local.exists() and f.md5 and _local_md5(local) == f.md5:
                    continue
                log.info("qfc download", slug=slug, file=f.name, target=str(local))
                await _download(client, project_id, f.name, local)
                project_changed = True

            if project_changed:
                changed += 1
                log.info("qfc synced", slug=slug)

    return changed


async def sync_loop() -> None:
    """Long-running task: sync every QFC_SYNC_INTERVAL_MINUTES."""
    interval = max(60, config.QFC_SYNC_INTERVAL_MINUTES * 60)
    while True:
        try:
            await sync_once()
        except Exception as e:  # noqa: BLE001
            log.error("qfc sync_once exception", error=str(e))
        await asyncio.sleep(interval)
