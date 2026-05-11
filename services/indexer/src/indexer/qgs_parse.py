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
from typing import Literal


# QGIS renderer-v2 type → short symbology kind. Anything unknown → "single".
_RENDERER_KIND: dict[str, str] = {
    "singleSymbol":           "single",
    "categorizedSymbol":      "categorized",
    "graduatedSymbol":        "graduated",
    "RuleRenderer":           "rule",
    "heatmapRenderer":        "heatmap",
    "invertedPolygonRenderer": "inverted",
    "pointDisplacement":      "displacement",
    "pointCluster":           "cluster",
    "25dRenderer":            "25d",
    "embeddedSymbol":         "embedded",
    "nullSymbol":             "none",
    "mergedFeatureRenderer":  "merged",
}

GeomKind = Literal["Point", "Line", "Polygon", "Raster", "NoGeometry"]


@dataclass(slots=True)
class Symbology:
    """Distilled symbology for one map layer.

    Captures *just enough* for the web UI to draw a legend swatch +
    show what kind of styling the QGIS author used. Full SLD/QML
    is left to py-qgis-server.
    """
    kind: str          # "single" | "categorized" | "graduated" | "rule" | "heatmap" | …
    class_count: int   # 1 for single, N for categorized/graduated/rule
    primary_color: str | None  # "#rrggbb" — first symbol's solid fill/stroke if discoverable
    attr: str | None   # categorized/graduated grouping attribute, if present


@dataclass(slots=True)
class Layer:
    id: str
    name: str
    datasource: str | None
    crs: str | None
    layer_type: str  # "vector" | "raster"
    geom_type: str | None
    wms_visible: bool
    symbology: Symbology | None = None


@dataclass(slots=True)
class TreeNode:
    """One node in the QGIS layer-tree. Either a group (with children)
    or a leaf reference to a layer id (children empty).
    """
    kind: Literal["group", "layer"]
    name: str
    layer_id: str | None = None         # leaf only
    expanded: bool = True
    checked: bool = True                # group/leaf default checked state
    children: list["TreeNode"] = field(default_factory=list)


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
    qgs_file: str = ""  # basename, e.g. "cuxhaven.qgz" or "cuxhaven_lite.qgs"
    layers: list[Layer] = field(default_factory=list)
    tree: TreeNode | None = None
    themes: list[Theme] = field(default_factory=list)
    print_layouts: list[str] = field(default_factory=list)


# ─── XML helpers ─────────────────────────────────────────────────────

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


# ─── Renderer / symbology extraction ─────────────────────────────────

def _parse_qgis_color(s: str | None) -> str | None:
    """QGIS encodes colors as either '#rrggbb', 'r,g,b' or 'r,g,b,a'."""
    if not s:
        return None
    s = s.strip()
    if s.startswith("#") and len(s) >= 7:
        return s[:7].lower()
    parts = s.split(",")
    if len(parts) >= 3:
        try:
            r, g, b = (max(0, min(255, int(float(p)))) for p in parts[:3])
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, TypeError):
            return None
    return None


def _first_symbol_color(symbol_el: ET.Element) -> str | None:
    """Walk a <symbol> element, return the first solid color we can find.

    QGIS symbols are recursive (SimpleFill > SimpleLine > ...) — we just
    take whichever <prop>/<Option> says "color" first.
    """
    # Modern (>=3.18) <Option type="QString" name="color" value="183,28,28,255,rgb:..."/>
    for opt in symbol_el.iter("Option"):
        if opt.get("name") == "color":
            color = _parse_qgis_color(opt.get("value"))
            if color:
                return color
    # Older <prop k="color" v="..."/>
    for prop in symbol_el.iter("prop"):
        if prop.get("k") == "color":
            color = _parse_qgis_color(prop.get("v"))
            if color:
                return color
    return None


def _extract_symbology(maplayer: ET.Element) -> Symbology | None:
    """Distill QGIS renderer-v2 / pipe block into a Symbology record."""
    # Vector renderer-v2
    rv2 = maplayer.find("renderer-v2")
    if rv2 is not None:
        raw_kind = rv2.get("type") or ""
        kind = _RENDERER_KIND.get(raw_kind, "single")
        attr = rv2.get("attr") or None
        # Class count: <categories>/<category>, <ranges>/<range>, <rules>/<rule>
        class_count = 1
        if kind == "categorized":
            class_count = len(rv2.findall(".//category"))
        elif kind == "graduated":
            class_count = len(rv2.findall(".//range"))
        elif kind == "rule":
            class_count = len(rv2.findall(".//rule"))
        elif kind == "heatmap":
            class_count = 0  # gradient — no discrete classes
        primary_color: str | None = None
        # Hunt for a representative color: first <symbol> we find inside.
        for sym in rv2.iter("symbol"):
            primary_color = _first_symbol_color(sym)
            if primary_color:
                break
        return Symbology(
            kind=kind,
            class_count=max(class_count, 0),
            primary_color=primary_color,
            attr=attr,
        )

    # Raster renderer
    rr = maplayer.find("pipe/rasterrenderer") or maplayer.find("rasterrenderer")
    if rr is not None:
        raw_kind = rr.get("type") or ""
        kind = {
            "singlebandgray":      "raster-gray",
            "singlebandpseudocolor": "raster-pseudo",
            "singlebandcolordata": "raster-color",
            "multibandcolor":      "raster-rgb",
            "paletted":            "raster-paletted",
            "hillshade":           "raster-hillshade",
            "contour":             "raster-contour",
        }.get(raw_kind, "raster")
        return Symbology(kind=kind, class_count=1, primary_color=None, attr=None)

    return None


# ─── Layer tree extraction ───────────────────────────────────────────

def _parse_tree(node: ET.Element) -> TreeNode:
    name = node.get("name") or ""
    if node.tag == "layer-tree-group":
        n = TreeNode(
            kind="group",
            name=name,
            expanded=node.get("expanded", "1") != "0",
            checked=node.get("checked", "Qt::Checked") != "Qt::Unchecked",
        )
        for c in node:
            if c.tag in ("layer-tree-group", "layer-tree-layer"):
                n.children.append(_parse_tree(c))
        return n
    # layer-tree-layer
    return TreeNode(
        kind="layer",
        name=name,
        layer_id=node.get("id"),
        expanded=node.get("expanded", "1") != "0",
        checked=node.get("checked", "Qt::Checked") != "Qt::Unchecked",
    )


# ─── Main entry ──────────────────────────────────────────────────────

def parse_qgs(qgs_path: Path, *, slug: str | None = None) -> ProjectMeta:
    tree = _open_qgs(qgs_path)
    root = tree.getroot()

    title = root.get("projectname") or qgs_path.stem
    crs_el = root.find("./projectCrs/spatialrefsys")
    crs = _findtext(crs_el, "authid") or "EPSG:25832"

    bbox: tuple[float, float, float, float] | None = None
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
        if bbox and any(c != 0 for c in bbox):
            break
        bbox = None

    layers: list[Layer] = []
    for ml in root.findall("./projectlayers/maplayer"):
        layer_id = ml.findtext("id") or ""
        layer_type = ml.get("type") or "vector"
        geom_type = ml.get("geometry")
        srs_authid = _findtext(ml.find("./srs/spatialrefsys"), "authid")
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
                symbology=_extract_symbology(ml),
            )
        )

    tree_node: TreeNode | None = None
    root_tree = root.find("./layer-tree-group")
    if root_tree is not None:
        tree_node = _parse_tree(root_tree)

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
        qgs_file=qgs_path.name,
        layers=layers,
        tree=tree_node,
        themes=themes,
        print_layouts=print_layouts,
    )
