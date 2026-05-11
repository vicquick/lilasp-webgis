// Thin OpenLayers wrapper. Phase 0 uses plain OL Map + TileWMS; masterportalAPI's
// higher-level helpers (rawLayerList, layer factories, search) can be wired in
// later without changing this file's signature.
//
// Per ADR-0001 we deliberately don't fork POLAR. masterportalAPI is in
// package.json so we can adopt its layer factories incrementally.

import Map from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import { defaults as defaultControls, ScaleLine } from 'ol/control';

import type { ServiceProject } from './services-loader';

export interface BridgeMapConfig {
  containerId: string;
  project: ServiceProject;
}

function projectCenter(project: ServiceProject): [number, number] {
  if (project.bbox) {
    return [(project.bbox[0] + project.bbox[2]) / 2, (project.bbox[1] + project.bbox[3]) / 2];
  }
  return [500000, 5550000];
}

function projectLayers(project: ServiceProject): TileLayer<TileWMS>[] {
  return project.layers
    .filter((layer) => layer.wms_visible)
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
      });
      const tile = new TileLayer({ source });
      tile.set('id', `${project.slug}__${layer.id}`);
      tile.set('name', layer.name);
      return tile;
    });
}

export async function createProjectMap({ containerId, project }: BridgeMapConfig): Promise<Map> {
  const view = new View({
    projection: project.crs,
    center: projectCenter(project),
    extent: project.bbox ?? undefined,
    resolutions: [1000, 500, 250, 100, 50, 25, 10, 5, 2.5, 1, 0.5, 0.25],
    constrainResolution: true,
  });

  if (project.bbox) {
    view.fit(project.bbox);
  }

  return new Map({
    target: containerId,
    view,
    layers: projectLayers(project),
    controls: defaultControls().extend([new ScaleLine({ units: 'metric' })]),
  });
}
