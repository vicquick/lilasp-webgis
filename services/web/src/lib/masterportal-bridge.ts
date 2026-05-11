// Thin wrapper around @masterportal/masterportalapi.
// We deliberately do NOT pull in POLAR — see ADR-0001.
// masterportalAPI exposes `createMap` (OpenLayers map factory) and
// `rawLayerList` (services.json reader). We supply our own services.json
// shape but adapt it to masterportalAPI's expectations here.

import { createMap as mpCreate } from '@masterportal/masterportalapi';
import type { Map as OLMap } from 'ol';
import type { ServiceProject } from './services-loader';

export interface BridgeMapConfig {
  containerId: string;
  project: ServiceProject;
}

function toMasterportalLayerConf(project: ServiceProject) {
  // masterportalAPI consumes a flat list keyed by `id` with WMS/WFS shape.
  return project.layers.map((layer) => ({
    id: `${project.slug}__${layer.id}`,
    name: layer.name,
    typ: 'WMS' as const,
    url: layer.wms_url,
    layers: layer.wms_layer_name,
    format: 'image/png',
    version: '1.3.0',
    transparent: true,
    tilesize: '512',
    visibility: layer.wms_visible,
  }));
}

export async function createProjectMap({ containerId, project }: BridgeMapConfig): Promise<OLMap> {
  const layerConf = toMasterportalLayerConf(project);
  const mapConfig = {
    target: containerId,
    epsg: project.crs,
    startCenter: project.bbox
      ? [(project.bbox[0] + project.bbox[2]) / 2, (project.bbox[1] + project.bbox[3]) / 2]
      : [500000, 5550000],
    extent: project.bbox ?? undefined,
    layerConf,
    layerIds: project.layers.filter((l) => l.wms_visible).map((l) => `${project.slug}__${l.id}`),
    options: {
      resolutions: [1000, 500, 250, 100, 50, 25, 10, 5, 2.5, 1, 0.5, 0.25],
    },
  };
  // masterportalAPI returns the OL Map instance.
  return (await mpCreate(mapConfig)) as unknown as OLMap;
}
