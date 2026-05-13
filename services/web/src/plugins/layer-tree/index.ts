// Layer tree — nested groups mirroring the QGIS project structure,
// per-layer symbology swatches + renderer-type badges, tri-state group
// checkboxes that fan out to children.
//
// The indexer (qgs_parse.py) emits both a flat `layers` array and a
// `tree` of `{kind, name, children?|layer_id?}`. We walk the tree.

import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import type {
  ServiceLayer,
  ServiceProject,
  ServiceTreeNode,
  SymbologyKind,
} from '../../lib/services-loader';
import type { BuiltMap } from '../../lib/masterportal-bridge';

export type StatusKind = 'ok' | 'busy' | 'err';
export interface StatusReporter {
  set(kind: StatusKind, text: string): void;
}

// ─── helpers ────────────────────────────────────────────────────────

function escapeHtml(s: string): string {
  return s.replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' })[c]!);
}

/** Short human-readable label for a renderer kind. */
const KIND_LABEL: Partial<Record<SymbologyKind, string>> = {
  single:        'einfach',
  categorized:   'kategorisiert',
  graduated:     'abgestuft',
  rule:          'regelbasiert',
  heatmap:       'heatmap',
  inverted:      'invertiert',
  displacement:  'verteilt',
  cluster:       'cluster',
  '25d':         '2.5D',
  embedded:      'eingebettet',
  merged:        'merged',
  'raster':           'raster',
  'raster-gray':      'raster · grau',
  'raster-pseudo':    'raster · pseudo',
  'raster-color':     'raster · farbe',
  'raster-rgb':       'raster · rgb',
  'raster-paletted':  'raster · palette',
  'raster-hillshade': 'hillshade',
  'raster-contour':   'kontur',
};

function geomShape(geom: string | null | undefined): 'Point' | 'Line' | 'Polygon' | '' {
  if (!geom) return '';
  if (geom === 'Point' || geom === 'MultiPoint') return 'Point';
  if (geom === 'Line'  || geom === 'MultiLineString' || geom === 'LineString') return 'Line';
  if (geom === 'Polygon' || geom === 'MultiPolygon') return 'Polygon';
  return '';
}

function layerRowHtml(layer: ServiceLayer, checked: boolean): string {
  const safe = escapeHtml(layer.name);
  const shape = geomShape(layer.geom_type);
  const kind: SymbologyKind = layer.symbology?.kind ?? (layer.type === 'raster' ? 'raster' : 'single');
  const color = layer.symbology?.primary_color ?? '';
  const styleAttr = color ? ` style="--swatch-color:${color}"` : '';
  const classes = layer.symbology?.class_count ?? 0;
  const kindShort = KIND_LABEL[kind] ?? kind;
  // Show the short kind label only when it's *not* trivially "einfach"
  // — saves visual noise on the 80% of layers that are single-symbol.
  const showKind = kind !== 'single' && layer.type !== 'raster' || classes > 1;
  const kindBadge = showKind
    ? `<span class="layer-row__kind" title="Symbology: ${escapeHtml(kindShort)}${classes > 1 ? ` · ${classes} Klassen` : ''}">${escapeHtml(kindShort)}${classes > 1 ? ` · ${classes}` : ''}</span>`
    : '';

  return (
    `<label class="layer-row" data-id="${escapeHtml(layer.id)}">` +
      `<input type="checkbox" class="layer-row__cb" ${checked ? 'checked' : ''} data-id="${escapeHtml(layer.id)}" />` +
      `<span class="layer-row__swatch" data-shape="${shape}" data-kind="${kind}"${styleAttr}></span>` +
      `<span class="layer-row__name" title="${safe}">${safe}${kindBadge}</span>` +
      `<button class="layer-row__action" data-action="zoom" data-id="${escapeHtml(layer.id)}" title="Zur Layer-Ausdehnung" type="button">` +
        `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7M3 21l7-7"/></svg>` +
      `</button>` +
    `</label>`
  );
}

/** Build a `data-collapsed` group with nested rows. */
function groupHtml(node: ServiceTreeNode, layerById: Map<string, ServiceLayer>, depth: number, leafCount: number): string {
  const safe = escapeHtml(node.name || '(unbenannt)');
  const collapsed = !node.expanded ? 'true' : 'false';
  const children = (node.children ?? [])
    .map((c) => renderNode(c, layerById, depth + 1))
    .join('');
  return (
    `<section class="layer-group" data-collapsed="${collapsed}">` +
      `<div class="layer-group__head" role="button" tabindex="0">` +
        `<span class="layer-group__caret">` +
          `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>` +
        `</span>` +
        `<input type="checkbox" class="layer-group__cb" />` +
        `<span class="layer-group__name" title="${safe}">${safe}</span>` +
        `<span class="layer-group__count">${leafCount}</span>` +
      `</div>` +
      `<div class="layer-group__children">${children}</div>` +
    `</section>`
  );
}

function renderableLeaves(node: ServiceTreeNode, layerById: Map<string, ServiceLayer>): ServiceLayer[] {
  if (node.kind === 'layer') {
    const l = node.layer_id ? layerById.get(node.layer_id) : undefined;
    return l && l.geom_type !== 'No geometry' ? [l] : [];
  }
  return (node.children ?? []).flatMap((c) => renderableLeaves(c, layerById));
}

function renderNode(node: ServiceTreeNode, layerById: Map<string, ServiceLayer>, depth: number): string {
  if (node.kind === 'layer') {
    const l = node.layer_id ? layerById.get(node.layer_id) : undefined;
    if (!l || l.geom_type === 'No geometry') return '';
    return layerRowHtml(l, false);
  }
  const leafCount = renderableLeaves(node, layerById).length;
  if (!leafCount) return ''; // collapse groups that contain only no-geom leaves
  return groupHtml(node, layerById, depth, leafCount);
}

/** Fallback: render a flat list if no tree was emitted (old indexer). */
function renderFlat(project: ServiceProject): string {
  return project.layers
    .filter((l) => l.geom_type !== 'No geometry')
    .map((l) => layerRowHtml(l, false))
    .join('');
}

// ─── mount ──────────────────────────────────────────────────────────

export function mountLayerTree(
  container: HTMLElement,
  builtMap: BuiltMap,
  project: ServiceProject,
  countEl?: HTMLElement | null,
  status?: StatusReporter,
): void {
  const layerById = new Map(project.layers.map((l) => [l.id, l]));
  const renderable = project.layers.filter((l) => l.geom_type !== 'No geometry');

  if (!renderable.length) {
    container.innerHTML = '<div class="layer-tree__empty">Keine Layer mit Geometrie.</div>';
    if (countEl) countEl.textContent = '0';
    return;
  }

  const treeHtml = project.tree
    ? renderNode(project.tree, layerById, 0) || renderFlat(project)
    : renderFlat(project);

  container.classList.add('layer-tree');
  container.innerHTML = treeHtml;
  if (countEl) countEl.textContent = `${renderable.length}`;

  // ── tile loading indicator ───────────────────────────────────────
  let inflight = 0;
  const flush = () => {
    if (!status) return;
    if (inflight === 0) status.set('ok', 'bereit');
    else status.set('busy', `WMS · ${inflight}`);
  };

  builtMap.map.getAllLayers().forEach((lyr) => {
    if (!lyr.get('webgis-layer')) return;
    const wms = lyr as TileLayer<TileWMS>;
    const src = wms.getSource();
    if (!src) return;
    const layerId = lyr.get('layer-id') as string;
    const row = () => container.querySelector<HTMLLabelElement>(`.layer-row[data-id="${CSS.escape(layerId)}"]`);
    src.on('tileloadstart', () => {
      inflight++; flush();
      row()?.setAttribute('data-loading', 'true');
    });
    const done = () => {
      inflight = Math.max(0, inflight - 1); flush();
      row()?.setAttribute('data-loading', 'false');
    };
    src.on('tileloadend', done);
    src.on('tileloaderror', () => {
      done();
      row()?.setAttribute('data-error', 'true');
    });
  });

  // ── interaction: group caret toggles, tri-state checkboxes ───────

  const refreshGroupStates = () => {
    container.querySelectorAll<HTMLElement>('.layer-group').forEach((g) => {
      const cb = g.querySelector<HTMLInputElement>(':scope > .layer-group__head > .layer-group__cb');
      if (!cb) return;
      const childChecks = g.querySelectorAll<HTMLInputElement>('.layer-row__cb');
      const total = childChecks.length;
      let on = 0;
      childChecks.forEach((c) => { if (c.checked) on++; });
      cb.checked = total > 0 && on === total;
      cb.indeterminate = on > 0 && on < total;
    });
  };

  container.addEventListener('click', (e) => {
    const target = e.target as HTMLElement;
    if (target.closest('.layer-row__cb, .layer-group__cb, .layer-row__action')) return;
    const head = target.closest<HTMLElement>('.layer-group__head');
    if (head) {
      const group = head.closest<HTMLElement>('.layer-group');
      if (group) {
        const collapsed = group.getAttribute('data-collapsed') === 'true';
        group.setAttribute('data-collapsed', collapsed ? 'false' : 'true');
      }
    }
  });

  container.addEventListener('change', (e) => {
    const t = e.target as HTMLInputElement;
    if (!(t instanceof HTMLInputElement) || t.type !== 'checkbox') return;
    if (t.classList.contains('layer-row__cb')) {
      const id = t.dataset.id!;
      builtMap.toggleLayer(`${project.slug}__${id}`, t.checked);
      refreshGroupStates();
    } else if (t.classList.contains('layer-group__cb')) {
      const group = t.closest('.layer-group');
      if (!group) return;
      const want = t.checked;
      group.querySelectorAll<HTMLInputElement>('.layer-row__cb').forEach((cb) => {
        if (cb.checked !== want) {
          cb.checked = want;
          const id = cb.dataset.id!;
          builtMap.toggleLayer(`${project.slug}__${id}`, want);
        }
      });
      refreshGroupStates();
    }
  });

  // zoom-to-extent action — best effort: use the project bbox for now.
  container.addEventListener('click', (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLButtonElement>('.layer-row__action[data-action="zoom"]');
    if (!btn) return;
    e.preventDefault();
    builtMap.fitToProject();
  });

  refreshGroupStates();
}

// ─── theme / preset application (preserves group collapse state) ────

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
  container.dispatchEvent(new Event('change', { bubbles: true }));
}

export interface ApplyThemeReport {
  themeName: string;
  /** Total renderable rows ON after applying. */
  activeCount: number;
  /** Layer IDs in the theme that have no renderable row (lookup tables etc.) */
  missing: string[];
}

export function applyTheme(
  container: HTMLElement,
  builtMap: BuiltMap,
  project: ServiceProject,
  themeName: string,
): ApplyThemeReport {
  const theme = project.themes.find((t) => t.name === themeName);
  if (!theme) return { themeName, activeCount: 0, missing: [] };
  const want = new Set(theme.visible_layer_ids);
  const styles = theme.layer_styles ?? {};
  let activeCount = 0;
  const seen = new Set<string>();
  container.querySelectorAll<HTMLInputElement>('input.layer-row__cb').forEach((cb) => {
    const id = cb.dataset.id!;
    seen.add(id);
    const visible = want.has(id);
    if (visible) activeCount++;
    cb.checked = visible;
    const mapLayerId = `${project.slug}__${id}`;
    // Update the named style BEFORE toggling visibility so the first
    // GetMap request after the layer turns on already carries the
    // theme's style — no double-fetch with the default style first.
    builtMap.setLayerStyle(mapLayerId, styles[id] ?? '');
    builtMap.toggleLayer(mapLayerId, visible);
  });
  const missing = [...want].filter((id) => !seen.has(id));
  // Trigger group tri-state recompute via a bubbling change.
  container.dispatchEvent(new Event('change', { bubbles: true }));
  return { themeName, activeCount, missing };
}
