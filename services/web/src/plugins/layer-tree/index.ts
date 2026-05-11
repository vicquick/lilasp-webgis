// Layer tree with checkboxes + legend swatches. Flat for now;
// QGIS layer groups can be parsed from <layer-tree-group> in a later pass.

import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import type { ServiceLayer, ServiceProject } from '../../lib/services-loader';
import type { BuiltMap } from '../../lib/masterportal-bridge';

export type StatusKind = 'ok' | 'busy' | 'err';
export interface StatusReporter {
  set(kind: StatusKind, text: string): void;
}

function rowHtml(layer: ServiceLayer): string {
  const safe = layer.name.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c]!);
  const geomAttr = layer.geom_type ? ` data-geom="${layer.geom_type}"` : '';
  const typeAttr = ` data-type="${layer.type}"`;
  const checked = layer.wms_visible ? 'checked' : '';
  return (
    `<label class="layer-row" data-id="${layer.id}">` +
    `<input type="checkbox" class="layer-row__cb" ${checked} data-id="${layer.id}" />` +
    `<span class="layer-row__swatch"${geomAttr}${typeAttr}></span>` +
    `<span class="layer-row__name" title="${safe}">${safe}</span>` +
    `<button class="layer-row__action" data-action="zoom" data-id="${layer.id}" title="Zur Layer-Ausdehnung">` +
    `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7M3 21l7-7"/></svg>` +
    `</button>` +
    `</label>`
  );
}

export function mountLayerTree(
  container: HTMLElement,
  builtMap: BuiltMap,
  project: ServiceProject,
  countEl?: HTMLElement | null,
  status?: StatusReporter,
): void {
  const layers = project.layers.filter((l) => l.geom_type !== 'No geometry');
  if (!layers.length) {
    container.innerHTML = '<div class="layer-tree__empty">Keine Layer mit Geometrie.</div>';
    if (countEl) countEl.textContent = '0';
    return;
  }
  // Render all checkboxes UNCHECKED. The map renders the basemap
  // immediately and the user opts-in per layer; this dodges the 46×
  // simultaneous WMS GetMap pile-up on cold start.
  container.innerHTML = layers
    .map((l) => rowHtml({ ...l, wms_visible: false }))
    .join('');
  if (countEl) countEl.textContent = `${layers.length}`;

  let inflight = 0;
  const flush = () => {
    if (!status) return;
    if (inflight === 0) status.set('ok', 'bereit');
    else status.set('busy', `WMS lädt · ${inflight}`);
  };

  // Wire per-layer tileload events to a loading indicator.
  builtMap.map.getAllLayers().forEach((lyr) => {
    if (!lyr.get('planportal-layer')) return;
    const wms = lyr as TileLayer<TileWMS>;
    const src = wms.getSource();
    if (!src) return;
    const layerId = lyr.get('layer-id') as string;
    const row = () => container.querySelector<HTMLLabelElement>(`.layer-row[data-id="${CSS.escape(layerId)}"]`);
    src.on('tileloadstart', () => {
      inflight++;
      flush();
      row()?.setAttribute('data-loading', 'true');
    });
    const done = () => {
      inflight = Math.max(0, inflight - 1);
      flush();
      const r = row();
      if (r && !src.getTileLoadFunction()) return;
      r?.setAttribute('data-loading', 'false');
    };
    src.on('tileloadend', done);
    src.on('tileloaderror', () => {
      done();
      row()?.setAttribute('data-error', 'true');
    });
  });

  container.addEventListener('change', (e) => {
    const t = e.target as HTMLInputElement;
    if (!(t instanceof HTMLInputElement) || t.type !== 'checkbox') return;
    const id = t.dataset.id!;
    builtMap.toggleLayer(`${project.slug}__${id}`, t.checked);
  });
}

export function setAllLayers(
  container: HTMLElement,
  builtMap: BuiltMap,
  project: ServiceProject,
  mode: 'qgis-default' | 'none',
): void {
  container.querySelectorAll<HTMLInputElement>('input.layer-row__cb').forEach((cb) => {
    const id = cb.dataset.id!;
    let visible = false;
    if (mode === 'qgis-default') {
      const layer = project.layers.find((l) => l.id === id);
      visible = Boolean(layer?.wms_visible);
    }
    cb.checked = visible;
    builtMap.toggleLayer(`${project.slug}__${id}`, visible);
  });
}

export function applyTheme(
  container: HTMLElement,
  builtMap: BuiltMap,
  project: ServiceProject,
  themeName: string,
): void {
  const theme = project.themes.find((t) => t.name === themeName);
  if (!theme) return;
  const want = new Set(theme.visible_layer_ids);
  container.querySelectorAll<HTMLInputElement>('input.layer-row__cb').forEach((cb) => {
    const id = cb.dataset.id!;
    const visible = want.has(id);
    cb.checked = visible;
    builtMap.toggleLayer(`${project.slug}__${id}`, visible);
  });
}
