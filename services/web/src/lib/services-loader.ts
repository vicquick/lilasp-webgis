// Loads /services.json (emitted by the indexer) and exposes typed accessors.

export type SymbologyKind =
  | 'single'
  | 'categorized'
  | 'graduated'
  | 'rule'
  | 'heatmap'
  | 'inverted'
  | 'displacement'
  | 'cluster'
  | '25d'
  | 'embedded'
  | 'merged'
  | 'none'
  | 'raster'
  | 'raster-gray'
  | 'raster-pseudo'
  | 'raster-color'
  | 'raster-rgb'
  | 'raster-paletted'
  | 'raster-hillshade'
  | 'raster-contour';

export interface ServiceSymbology {
  kind: SymbologyKind;
  class_count: number;
  primary_color: string | null;
  attr: string | null;
}

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
  symbology: ServiceSymbology | null;
}

export interface ServiceTreeNode {
  kind: 'group' | 'layer';
  name: string;
  expanded: boolean;
  checked: boolean;
  /** Only for kind="layer" */
  layer_id?: string;
  /** Only for kind="group" */
  children?: ServiceTreeNode[];
}

export interface ServiceTheme {
  name: string;
  visible_layer_ids: string[];
  /** Per-layer named-style override (passed verbatim to WMS `STYLES=`).
      Absent entries → the layer's default style is used. */
  layer_styles: Record<string, string>;
  /** Group paths to expand under this theme (e.g. "ALKIS/Straßennetzwerk"). */
  expanded_groups: string[];
  /** Group paths to render as checked (group tri-state := all-on under this theme). */
  checked_groups: string[];
}

export interface ServiceProject {
  slug: string;
  title: string;
  crs: string;
  bbox: [number, number, number, number] | null;
  qgs_file?: string;
  layers: ServiceLayer[];
  tree: ServiceTreeNode | null;
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
