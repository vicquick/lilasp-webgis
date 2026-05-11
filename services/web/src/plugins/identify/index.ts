// Identify-on-click. Hits py-qgis-server's WMS GetFeatureInfo for every
// visible layer on the map at the click location, populates the
// inspector right-panel with the merged results.

import type { Map as OLMap } from 'ol';
import TileWMS from 'ol/source/TileWMS';
import TileLayer from 'ol/layer/Tile';
import type { ServiceProject } from '../../lib/services-loader';

interface IdentifyFeature {
  layerName: string;
  properties: Record<string, string>;
}

function escapeHtml(s: string): string {
  return s.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c]!);
}

function renderFeatures(features: IdentifyFeature[]): string {
  if (!features.length) {
    return '<div class="empty-state">Hier liegt keine Information vor.</div>';
  }
  return features
    .map(
      (f) =>
        `<article class="feature">` +
        `<h3 class="feature__title">${escapeHtml(f.layerName)}</h3>` +
        `<dl>` +
        Object.entries(f.properties)
          .filter(([, v]) => v != null && String(v) !== '')
          .map(
            ([k, v]) =>
              `<div class="feature__row"><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd></div>`,
          )
          .join('') +
        `</dl>` +
        `</article>`,
    )
    .join('');
}

export function mountIdentify(
  map: OLMap,
  _project: ServiceProject,
  inspector: {
    open: (title: string, html: string) => void;
    setBusy: (busy: boolean) => void;
  },
): void {
  map.on('singleclick', async (evt) => {
    const view = map.getView();
    const resolution = view.getResolution();
    const projection = view.getProjection().getCode();
    if (resolution == null) return;

    inspector.open('Objekt-Info', '<div class="empty-state">Lade…</div>');
    inspector.setBusy(true);

    const results: IdentifyFeature[] = [];
    const layers = map
      .getAllLayers()
      .filter((l): l is TileLayer<TileWMS> => l.get('planportal-layer') === true && l.getVisible());

    for (const layer of layers) {
      const src = layer.getSource();
      if (!src) continue;
      const url = src.getFeatureInfoUrl(
        evt.coordinate,
        resolution,
        projection,
        { INFO_FORMAT: 'application/json', FEATURE_COUNT: 8 },
      );
      if (!url) continue;
      try {
        const r = await fetch(url, { credentials: 'include' });
        if (!r.ok) continue;
        const json = (await r.json()) as { features?: Array<{ id?: string; properties?: Record<string, unknown> }> };
        for (const feat of json.features ?? []) {
          const props = feat.properties ?? {};
          // GeoJSON FC features include a `layer` property hint from QGIS Server
          const layerName = (props.layer as string | undefined) ?? layer.get('name') ?? 'Layer';
          const cleaned: Record<string, string> = {};
          for (const [k, v] of Object.entries(props)) {
            if (k === 'layer') continue;
            cleaned[k] = String(v);
          }
          results.push({ layerName, properties: cleaned });
        }
      } catch {
        /* ignore per-layer failures */
      }
    }

    inspector.setBusy(false);
    inspector.open('Objekt-Info', renderFeatures(results));
  });
}
