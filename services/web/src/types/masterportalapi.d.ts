// masterportalAPI ships JS without type declarations. We only call the
// handful of functions documented in services/web/src/lib/masterportal-bridge.ts,
// so a minimal ambient declaration is enough.

declare module '@masterportal/masterportalapi' {
  import type { Map as OLMap } from 'ol';

  export interface MasterportalLayerConf {
    id: string;
    name: string;
    typ: 'WMS' | 'WFS' | 'WMTS' | 'GeoJSON' | 'VectorTile';
    url: string;
    layers?: string;
    format?: string;
    version?: string;
    transparent?: boolean;
    tilesize?: string | number;
    visibility?: boolean;
    [key: string]: unknown;
  }

  export interface MasterportalMapConfig {
    target: string;
    epsg: string;
    startCenter?: [number, number];
    extent?: [number, number, number, number];
    layerConf?: MasterportalLayerConf[];
    layerIds?: string[];
    options?: {
      resolutions?: number[];
      [key: string]: unknown;
    };
    [key: string]: unknown;
  }

  export function createMap(config: MasterportalMapConfig): Promise<OLMap>;
}
