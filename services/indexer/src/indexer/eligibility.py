"""Decide whether a layer's QML style can be safely translated to MapLibre.

A layer is vector-tile-eligible only if its symbolisation fits the subset
of QGIS that round-trips through geostyler-cli without loss. See
docs/research/01-stack-deep-dive.md §3 for the full reasoning.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

_OK_RENDERERS = {"singleSymbol", "categorizedSymbol", "graduatedSymbol", "RuleRenderer"}
_OK_SYMBOL_LAYERS = {
    "SimpleMarker",
    "SimpleLine",
    "SimpleFill",
    "SimpleFillSymbolLayerV2",
}


def is_vector_tile_eligible(layer_type: str, qml_path: Path | None) -> tuple[bool, str]:
    """Returns (eligible, reason). reason is empty when eligible."""
    if layer_type != "vector":
        return False, "non-vector layer"
    if qml_path is None or not qml_path.exists():
        # No QML → assume server-side default style → cannot translate.
        return False, "no QML alongside layer"

    try:
        qml = ET.parse(qml_path).getroot()
    except ET.ParseError as e:
        return False, f"QML parse error: {e}"

    renderer = qml.find(".//renderer-v2")
    rtype = renderer.get("type") if renderer is not None else None
    if rtype not in _OK_RENDERERS:
        return False, f"renderer {rtype!r} not supported"

    for sl in qml.findall(".//symbol/layer"):
        cls = sl.get("class")
        if cls not in _OK_SYMBOL_LAYERS:
            return False, f"symbol layer {cls!r} not supported"
        for prop in sl.findall("Option/Option"):
            if prop.get("k") == "RenderMetersInMapUnits" and prop.get("v") == "1":
                return False, "RenderMetersInMapUnits"

    return True, ""
