// OpenLayers Map factory.
// Phase 0 uses plain OL Map + TileWMS + OSM/Carto basemap.
// masterportalAPI layer factories will be folded in once we wire WFS-T edit.

import Map from 'ol/Map';
import View from 'ol/View';
import { transformExtent } from 'ol/proj';
import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import OSM from 'ol/source/OSM';
import XYZ from 'ol/source/XYZ';
import { defaults as defaultControls, ScaleLine, Attribution } from 'ol/control';

import type { ServiceProject } from './services-loader';

export const BASEMAPS = {
  carto: {
    label: 'CARTO Voyager',
    url: 'https://{a-d}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
    attribution: '© CARTO · © OpenStreetMap',
    maxZoom: 19,
  },
  osm: {
    label: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap',
    maxZoom: 19,
  },
  esriSat: {
    label: 'Satellit (Esri)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '© Esri · Maxar · Earthstar Geographics',
    maxZoom: 19,
  },
} as const;
export type BasemapKey = keyof typeof BASEMAPS;

function buildBasemap(key: BasemapKey): TileLayer<XYZ | OSM> {
  if (key === 'osm') {
    const layer = new TileLayer({ source: new OSM() });
    layer.set('basemap', true);
    layer.set('basemap-key', 'osm');
    return layer;
  }
  const cfg = BASEMAPS[key];
  const layer = new TileLayer({
    source: new XYZ({
      url: cfg.url,
      attributions: cfg.attribution,
      crossOrigin: 'anonymous',
      maxZoom: cfg.maxZoom,
    }),
  });
  layer.set('basemap', true);
  layer.set('basemap-key', key);
  return layer;
}

/**
 * Build OL tile layers for every renderable QGIS layer in the project.
 * Cold-start aware:
 *   - Layers default to `visible: false` so the first paint is just the
 *     basemap (instant) and the user opts-in per layer.
 *   - QGIS layer visibility from the .qgs is preserved in a custom
 *     property `wms-default-visible` so the map-theme switcher and
 *     layer-tree can honour it without forcing 46 simultaneous WMS
 *     requests at first paint.
 */
function projectLayers(project: ServiceProject): TileLayer<TileWMS>[] {
  return project.layers
    .filter((l) => l.type === 'vector' || l.type === 'raster')
    .filter((l) => l.geom_type !== 'No geometry')
    .map((layer) => {
      const source = new TileWMS({
        url: layer.wms_url,
        params: {
          LAYERS: layer.wms_layer_name,
          FORMAT: 'image/png',
          TRANSPARENT: true,
          VERSION: '1.3.0',
        },
        crossOrigin: 'anonymous',
        serverType: 'qgis',
        transition: 0,
      });
      const tile = new TileLayer({
        source,
        visible: false,
        opacity: 1,
        properties: {
          id: `${project.slug}__${layer.id}`,
          name: layer.name,
          'layer-id': layer.id,
          'wms-default-visible': layer.wms_visible,
          'planportal-layer': true,
        },
      });
      return tile;
    });
}

const GERMANY_BBOX_4326: [number, number, number, number] = [5.5, 47.0, 15.5, 55.5];

export interface BuiltMap {
  map: Map;
  setBasemap: (key: BasemapKey) => void;
  toggleLayer: (id: string, visible: boolean) => void;
  fitToProject: () => void;
}

export function createProjectMap(containerId: string, project: ServiceProject): BuiltMap {
  // Project extent fallback: if .qgs had no extent, fit to a Germany-wide bbox
  // reprojected from EPSG:4326 to the project's CRS. The user can still zoom.
  let extent: [number, number, number, number] | undefined = project.bbox ?? undefined;
  if (!extent) {
    try {
      extent = transformExtent(GERMANY_BBOX_4326, 'EPSG:4326', project.crs) as [number, number, number, number];
    } catch {
      extent = undefined;
    }
  }

  const view = new View({
    projection: project.crs,
    constrainResolution: true,
    smoothExtentConstraint: true,
    showFullExtent: true,
  });

  const basemap = buildBasemap('carto');
  const wms = projectLayers(project);

  const map = new Map({
    target: containerId,
    view,
    layers: [basemap, ...wms],
    controls: defaultControls({ zoom: false, attribution: false }).extend([
      new ScaleLine({ units: 'metric' }),
      new Attribution({ collapsible: false }),
    ]),
  });

  if (extent) {
    view.fit(extent, { padding: [40, 40, 40, 40], maxZoom: 18 });
  } else {
    view.setCenter([500000, 5550000]);
    view.setZoom(6);
  }

  return {
    map,
    setBasemap(key) {
      basemap.setSource(buildBasemap(key).getSource() as any);
      basemap.set('basemap-key', key);
    },
    toggleLayer(id, visible) {
      const lyr = map.getAllLayers().find((l) => l.get('id') === id);
      lyr?.setVisible(visible);
    },
    fitToProject() {
      if (extent) view.fit(extent, { padding: [40, 40, 40, 40], duration: 250, maxZoom: 18 });
    },
  };
}
