from pathlib import Path
from textwrap import dedent

import pytest

from indexer.qgs_parse import parse_qgs


SAMPLE_QGS = dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<qgis projectname="Demo">
  <projectCrs>
    <spatialrefsys>
      <authid>EPSG:25832</authid>
    </spatialrefsys>
  </projectCrs>
  <ProjectViewSettings>
    <Extent>
      <xmin>460000</xmin><ymin>5540000</ymin>
      <xmax>490000</xmax><ymax>5570000</ymax>
    </Extent>
  </ProjectViewSettings>
  <projectlayers>
    <maplayer type="vector" geometry="Polygon">
      <id>spielplaetze_abc</id>
      <layername>Spielplätze</layername>
      <datasource>./data/spielplaetze.shp</datasource>
      <srs><spatialrefsys><authid>EPSG:25832</authid></spatialrefsys></srs>
      <flags><Identifiable>1</Identifiable></flags>
    </maplayer>
  </projectlayers>
  <visibility-presets>
    <visibility-preset name="Übersicht">
      <layer id="spielplaetze_abc" visible="1"/>
    </visibility-preset>
  </visibility-presets>
  <Layouts>
    <Layout name="A4 Quer"/>
  </Layouts>
</qgis>
""")


def test_parse_qgs(tmp_path: Path) -> None:
    qgs = tmp_path / "demo.qgs"
    qgs.write_text(SAMPLE_QGS)

    meta = parse_qgs(qgs, slug="demo")

    assert meta.slug == "demo"
    assert meta.title == "Demo"
    assert meta.crs == "EPSG:25832"
    assert meta.bbox == (460000.0, 5540000.0, 490000.0, 5570000.0)
    assert len(meta.layers) == 1
    layer = meta.layers[0]
    assert layer.id == "spielplaetze_abc"
    assert layer.name == "Spielplätze"
    assert layer.layer_type == "vector"
    assert layer.crs == "EPSG:25832"
    assert layer.wms_visible is True
    assert len(meta.themes) == 1
    assert meta.themes[0].name == "Übersicht"
    assert meta.themes[0].visible_layer_ids == ["spielplaetze_abc"]
    assert meta.print_layouts == ["A4 Quer"]


def test_parse_qgs_missing_crs_defaults_to_25832(tmp_path: Path) -> None:
    qgs = tmp_path / "demo.qgs"
    qgs.write_text("<?xml version='1.0'?><qgis projectname='x'/>")
    meta = parse_qgs(qgs, slug="demo")
    assert meta.crs == "EPSG:25832"
    assert meta.layers == []
