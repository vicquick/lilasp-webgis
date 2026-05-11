"""Handle the LL-WIE-2427-style self-contained zip.

The zip ships with one or more `.shp` layers and a sidecar `.styles.json`
keyed by layer id with base64-encoded `.qml` blobs. On ingest we:

1. Extract everything into `/srv/gis/<slug>/`
2. Decode the QML sidecars into `<slug>/styles/<layer_id>.qml`
3. Synthesise a stub `.qgs` referencing the layers (if the zip didn't ship one)

The stub is intentionally minimal — QGIS Server reads it well enough to
serve WMS/WFS, and the human authoring workflow remains "open in QGIS
Desktop, save back".
"""
from __future__ import annotations

import base64
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.dom import minidom


def extract_qfield_zip(zip_path: Path, dest_root: Path) -> Path:
    """Extracts a self-contained zip to dest_root/<slug>/. Returns the .qgs path.

    If the zip already ships a .qgs/.qgz, it's used as-is. Otherwise we
    synthesise a stub .qgs that exposes every .shp it found.
    """
    slug = zip_path.stem
    dest = dest_root / slug
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)

    # Decode base64 QML sidecars if present.
    sidecar = next(dest.rglob("*.styles.json"), None)
    if sidecar:
        styles_dir = dest / "styles"
        styles_dir.mkdir(exist_ok=True)
        data = json.loads(sidecar.read_text())
        for layer_id, b64 in data.items():
            (styles_dir / f"{layer_id}.qml").write_bytes(base64.b64decode(b64))

    existing = next((p for p in dest.rglob("*.qgs")), None) or next(
        (p for p in dest.rglob("*.qgz")), None
    )
    if existing:
        # Move the .qgs to the top of the slug dir to make the indexer's
        # discovery path predictable.
        target = dest / existing.name
        if existing != target:
            shutil.move(str(existing), target)
        return target

    return _synthesise_stub_qgs(dest, slug)


def _synthesise_stub_qgs(dest: Path, slug: str) -> Path:
    """Build a minimal .qgs exposing every .shp under `dest`.

    The schema is intentionally narrow: QGIS Server only needs the layer
    tree + project CRS to serve a layer. Styles are loaded from sibling
    `.qml` (QGIS convention) or `styles/<id>.qml` if we decoded base64.
    """
    qgis = ET.Element("qgis", projectname=slug, version="3.40.0")

    crs_el = ET.SubElement(qgis, "projectCrs")
    srs = ET.SubElement(crs_el, "spatialrefsys")
    ET.SubElement(srs, "authid").text = "EPSG:25832"
    ET.SubElement(srs, "description").text = "ETRS89 / UTM zone 32N"

    project_layers = ET.SubElement(qgis, "projectlayers")
    layer_tree = ET.SubElement(qgis, "layer-tree-group")
    legend = ET.SubElement(qgis, "legend")

    for shp in sorted(dest.rglob("*.shp")):
        layer_id = shp.stem
        ml = ET.SubElement(
            project_layers,
            "maplayer",
            type="vector",
            geometry="Unknown",
        )
        ET.SubElement(ml, "id").text = layer_id
        ET.SubElement(ml, "layername").text = layer_id
        # Relative path from .qgs (we'll write .qgs at slug root).
        rel = shp.relative_to(dest).as_posix()
        ET.SubElement(ml, "datasource").text = f"./{rel}|layername={layer_id}"
        srs_l = ET.SubElement(ET.SubElement(ml, "srs"), "spatialrefsys")
        ET.SubElement(srs_l, "authid").text = "EPSG:25832"
        ET.SubElement(ET.SubElement(ml, "flags"), "Identifiable").text = "1"

        ET.SubElement(
            layer_tree,
            "layer-tree-layer",
            id=layer_id,
            name=layer_id,
            checked="Qt::Checked",
            providerKey="ogr",
            source=f"./{rel}",
        )

    qgs_path = dest / f"{slug}.qgs"
    pretty = minidom.parseString(ET.tostring(qgis, encoding="unicode")).toprettyxml(indent="  ")
    qgs_path.write_text(pretty)
    return qgs_path
