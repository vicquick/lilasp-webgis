// Loads /services.json (emitted by the indexer) and exposes typed accessors.

export interface ServiceLayer {
  id: string;
  name: string;
  type: 'vector' | 'raster';
  geom_type: string | null;
  crs: string | null;
  wms_visible: boolean;
  wms_url: string;
  wms_layer_name: string;
  wfs_url: string;
  pmtiles_url: string | null;
  style_url: string | null;
}

export interface ServiceTheme {
  name: string;
  visible_layer_ids: string[];
}

export interface ServiceProject {
  slug: string;
  title: string;
  crs: string;
  bbox: [number, number, number, number] | null;
  qgs_file?: string;
  layers: ServiceLayer[];
  themes: ServiceTheme[];
  print_layouts: string[];
  endpoints: { wms: string; wfs?: string; print: string };
}

export interface ServicesPayload {
  version: number;
  projects: ServiceProject[];
}

declare const __WEB_SERVICES_JSON_URL__: string;

export async function loadServices(): Promise<ServicesPayload> {
  const r = await fetch(__WEB_SERVICES_JSON_URL__, { credentials: 'include' });
  if (!r.ok) throw new Error(`services.json: HTTP ${r.status}`);
  return (await r.json()) as ServicesPayload;
}
