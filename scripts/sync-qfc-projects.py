#!/usr/bin/env python3
"""Sync QGIS projects from QFieldCloud into /var/www/qgis-projects/.

For every QFC project that maps to a WebGIS theme (see PROJECT_THEME_MAP),
download the main .qgs/.qgz and any referenced attachment archives.
After sync, trigger QWC config regeneration.

Usage:
  QFC_USER=admin QFC_PASS=... ./sync-qfc-projects.py [--dry-run] [--only <project>]

Runs idempotently: only overwrites when the remote file is newer than local.
Safe to schedule via cron (e.g. every 15 min).
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

QFC_BASE = os.environ.get("QFC_BASE_URL", "https://qfield.lilasp.de/api/v1").rstrip("/")
QFC_TOKEN = os.environ.get("QFC_ADMIN_TOKEN") or os.environ.get("QFC_TOKEN")
QFC_USER = os.environ.get("QFC_USER")
QFC_PASS = os.environ.get("QFC_PASS")
PROJECTS_DIR = Path(os.environ.get("QGIS_PROJECTS_DIR", "/var/www/qgis-projects"))
CONFIG_SERVICE_URL = os.environ.get(
    "CONFIG_SERVICE_URL",
    "http://qwc-config-service-v88wco4g4kws8848wgsgk0k0:9090",
)

# QFC project name → local file stem in /var/www/qgis-projects/
PROJECT_FILENAME_MAP: dict[str, str] = {
    "WIE_Spielplaetze": "LILASp_Wiesbaden_Spielplaetze",
    "CUX_Spielplaetze": "LILASp_Cuxhaven_Spielplaetze",
    "Cuxhaven_Spielplaetze": "LILASp_Cuxhaven_Spielplaetze",
    "FFM_Naturerlebnisprofile": "LILASp_Frankfurt_Naturerlebnisprofile",
    "FFM_Orte": "LILASp_Frankfurt_Orte",
    "FFM_Plaetze": "LILASp_Frankfurt_Plaetze",
    "FFM_Wege": "LILASp_Frankfurt_Wege",
    "Schnelsen_HCS_Baeume": "LILASp_Schnelsen_Baeume",
    # Kept for compatibility — existing FFEP project
    "FFM_FFEP": "LILASp_Frankfurt_FFEP",
}

log = logging.getLogger("sync-qfc")


def qfc_login() -> str:
    if QFC_TOKEN:
        return QFC_TOKEN
    if not QFC_USER or not QFC_PASS:
        sys.exit("Set QFC_ADMIN_TOKEN, or QFC_USER + QFC_PASS env vars")
    r = requests.post(f"{QFC_BASE}/auth/login/", json={"username": QFC_USER, "password": QFC_PASS}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def qfc_projects(token: str) -> list[dict]:
    r = requests.get(f"{QFC_BASE}/projects/", headers={"Authorization": f"Token {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def qfc_list_files(token: str, project_id: str) -> list[dict]:
    r = requests.get(
        f"{QFC_BASE}/files/{project_id}/",
        headers={"Authorization": f"Token {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def qfc_download_file(token: str, project_id: str, filename: str, dest: Path) -> None:
    url = f"{QFC_BASE}/files/{project_id}/{filename}/"
    with requests.get(url, headers={"Authorization": f"Token {token}"}, stream=True, timeout=120, allow_redirects=True) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 15):
                if chunk:
                    f.write(chunk)
        tmp.replace(dest)


def file_hash(p: Path) -> str:
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 15), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_project(token: str, project: dict, dry: bool) -> bool:
    """Returns True if anything changed."""
    qfc_name = project.get("name", "")
    project_id = project.get("id")
    mapped = PROJECT_FILENAME_MAP.get(qfc_name)
    if not mapped:
        log.debug("skip %s (not in PROJECT_FILENAME_MAP)", qfc_name)
        return False

    changed = False
    try:
        files = qfc_list_files(token, project_id)
    except requests.HTTPError as e:
        log.error("%s: cannot list files (%s)", qfc_name, e)
        return False

    # Find the main project file
    qgs_name = project.get("project_filename")
    if not qgs_name:
        qgs_candidates = [f["name"] for f in files if f.get("name", "").lower().endswith((".qgs", ".qgz"))]
        if not qgs_candidates:
            log.warning("%s: no .qgs/.qgz file found — skipping", qfc_name)
            return False
        if len(qgs_candidates) > 1:
            log.warning("%s: multiple .qgs/.qgz (%s) — picking first", qfc_name, qgs_candidates)
        qgs_name = qgs_candidates[0]

    # Main .qgs plus every non-QField-meta file the project might reference.
    # QField's cloud projects carry their lookup CSVs / shapefiles / gpkg
    # alongside the .qgs — all of these must land on disk or QGIS Server
    # rejects layers as invalid.
    SKIP_SUFFIXES = (".qfs",)
    SKIP_NAMES = {"attachments.zip"}
    wanted = [qgs_name]
    for f in files:
        fname = f.get("name", "")
        low = fname.lower()
        if fname == qgs_name:
            continue
        if low.endswith(SKIP_SUFFIXES):
            continue
        if low in SKIP_NAMES:
            continue
        # Skip the zipped attachments bundle (we sync individual files instead)
        if low.endswith("_attachments.zip"):
            continue
        wanted.append(fname)

    for fname in wanted:
        file_rec = next((f for f in files if f.get("name") == fname), None)
        if not file_rec:
            continue
        remote_md5 = file_rec.get("md5sum")
        ext = Path(fname).suffix or ".qgs"
        is_main = fname == qgs_name
        # Main .qgs → mapped name; data files → preserve original name/subdir
        # so relative references inside the .qgs resolve against /data/
        if is_main:
            local = PROJECTS_DIR / f"{mapped}{ext}"
        else:
            # fname may contain forward slashes (e.g. "Data/file.shp")
            local = PROJECTS_DIR / fname
            local.parent.mkdir(parents=True, exist_ok=True)

        if local.exists() and remote_md5:
            local_md5 = hashlib.md5(local.read_bytes()).hexdigest()
            if local_md5 == remote_md5:
                log.info("%s → %s: up-to-date", qfc_name, local.name)
                continue

        if dry:
            log.info("%s → %s: would download (remote=%s, local=%s)",
                     qfc_name, local.name, (remote_md5 or "?")[:8],
                     "missing" if not local.exists() else "differs")
            changed = True
            continue

        # Backup existing before overwrite
        if local.exists():
            bak = local.with_suffix(local.suffix + ".bak")
            shutil.copy2(local, bak)
            log.info("%s: backup → %s", qfc_name, bak.name)

        log.info("%s → %s: downloading", qfc_name, local.name)
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        qfc_download_file(token, project_id, fname, local)
        try:
            shutil.chown(local, user="www-data", group="www-data")
        except (PermissionError, LookupError):
            pass
        changed = True

    return changed


def trigger_config_regen() -> None:
    try:
        r = requests.get(f"{CONFIG_SERVICE_URL}/generate_configs?tenant=default", timeout=60)
        if r.ok:
            log.info("Config regen triggered: %s", r.json())
        else:
            log.warning("Config regen returned %s: %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        log.warning("Config regen trigger failed: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="Only sync this QFC project name")
    parser.add_argument("--no-regen", action="store_true", help="Do not trigger config regen")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("QFC sync starting (base=%s)", QFC_BASE)
    token = qfc_login()
    projects = qfc_projects(token)
    log.info("Found %d QFC projects", len(projects))

    any_changed = False
    for p in projects:
        if args.only and p.get("name") != args.only:
            continue
        if sync_project(token, p, dry=args.dry_run):
            any_changed = True

    if any_changed and not args.dry_run and not args.no_regen:
        log.info("Changes detected — regenerating QWC configs")
        trigger_config_regen()
    else:
        log.info("No changes — regen skipped")

    return 0


if __name__ == "__main__":
    sys.exit(main())
