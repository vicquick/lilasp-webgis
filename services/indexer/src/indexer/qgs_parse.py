"""Parse a `.qgs` (or inner .qgs of a `.qgz`) into project metadata.

Uses `xml.etree.ElementTree` — covers ≥95% of what we need without the
1 GB PyQGIS container. Separate validator container runs PyQGIS for the
remaining edge cases (periodic batch).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Layer:
    id: str
    name: str
    datasource: str | None
    crs: str | None
    layer_type: str  # "vector" | "raster"
    geom_type: str | None
    wms_visible: bool


@dataclass(slots=True)
class Theme:
    name: str
    visible_layer_ids: list[str]


@dataclass(slots=True)
class ProjectMeta:
    slug: str
    title: str
    crs: str
    bbox: tuple[float, float, float, float] | None
    layers: list[Layer] = field(default_factory=list)
    themes: list[Theme] = field(default_factory=list)
    print_layouts: list[str] = field(default_factory=list)


def _open_qgs(path: Path) -> ET.ElementTree:
    if path.suffix.lower() == ".qgz":
        with zipfile.ZipFile(path) as z:
            inner = next((n for n in z.namelist() if n.endswith(".qgs")), None)
            if not inner:
                raise ValueError(f"{path}: no .qgs inside .qgz")
            with z.open(inner) as f:
                return ET.parse(f)
    return ET.parse(path)


def _findtext(el: ET.Element | None, path: str, default: str | None = None) -> str | None:
    if el is None:
        return default
    found = el.findtext(path)
    return found if found is not None else default


def parse_qgs(qgs_path: Path, *, slug: str | None = None) -> ProjectMeta:
    tree = _open_qgs(qgs_path)
    root = tree.getroot()

    title = root.get("projectname") or qgs_path.stem
    crs_el = root.find("./projectCrs/spatialrefsys")
    crs = _findtext(crs_el, "authid") or "EPSG:25832"

    bbox: tuple[float, float, float, float] | None = None
    # Different QGIS versions put the extent in different places. Try
    # newest (ProjectViewSettings) → mapcanvas (3.x classic) → top-level.
    for xpath in (
        "./ProjectViewSettings/Extent",
        ".//mapcanvas/extent",
        "./extent",
    ):
        ext = root.find(xpath)
        if ext is None:
            continue
        try:
            bbox = (
                float(ext.findtext("xmin", "0") or 0),
                float(ext.findtext("ymin", "0") or 0),
                float(ext.findtext("xmax", "0") or 0),
                float(ext.findtext("ymax", "0") or 0),
            )
        except (ValueError, TypeError):
            bbox = None
        # Reject all-zero extents
        if bbox and any(c != 0 for c in bbox):
            break
        bbox = None

    layers: list[Layer] = []
    for ml in root.findall("./projectlayers/maplayer"):
        layer_id = ml.findtext("id") or ""
        layer_type = ml.get("type") or "vector"
        geom_type = ml.get("geometry")
        srs_authid = _findtext(ml.find("./srs/spatialrefsys"), "authid")
        # Identifiable flag controls WMS GetFeatureInfo + visibility in legend.
        identifiable = ml.findtext("./flags/Identifiable")
        layers.append(
            Layer(
                id=layer_id,
                name=ml.findtext("layername") or layer_id,
                datasource=ml.findtext("datasource"),
                crs=srs_authid,
                layer_type=layer_type,
                geom_type=geom_type,
                wms_visible=identifiable != "0",
            )
        )

    themes: list[Theme] = []
    for preset in root.findall(".//visibility-presets/visibility-preset"):
        themes.append(
            Theme(
                name=preset.get("name") or "",
                visible_layer_ids=[
                    layer.get("id") or ""
                    for layer in preset.findall("./layer")
                    if layer.get("visible") == "1" and layer.get("id")
                ],
            )
        )

    print_layouts = [
        layout.get("name") or ""
        for layout in root.findall(".//Layouts/Layout")
        if layout.get("name")
    ]
    # Older QGIS files store layouts under .//Layout (no parent Layouts node).
    if not print_layouts:
        print_layouts = [
            layout.get("name") or ""
            for layout in root.findall(".//Layout")
            if layout.get("name")
        ]

    return ProjectMeta(
        slug=slug or qgs_path.parent.name,
        title=title,
        crs=crs,
        bbox=bbox,
        layers=layers,
        themes=themes,
        print_layouts=print_layouts,
    )
