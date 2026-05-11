// GetPrint dialog mounted in the inspector. Opens server-rendered PDF in
// a new tab using the QGIS project's own print layouts.

import type { Map as OLMap } from 'ol';
import type { ServiceProject } from '../../lib/services-loader';

declare const __WEB_QGIS_BASE__: string;

export function renderPrintForm(project: ServiceProject): string {
  if (!project.print_layouts.length) {
    return '<div class="empty-state">Keine Drucklayouts in diesem Projekt.</div>';
  }
  return (
    `<form class="print-form" id="print-form">` +
    `<div class="print-form__field">` +
    `<label for="print-layout">Layout</label>` +
    `<select id="print-layout">` +
    project.print_layouts.map((l) => `<option value="${l}">${l.replace(/_/g, ' ')}</option>`).join('') +
    `</select>` +
    `</div>` +
    `<div class="print-form__field">` +
    `<label for="print-dpi">DPI</label>` +
    `<select id="print-dpi"><option value="96">Bildschirm (96)</option><option value="150" selected>Standard (150)</option><option value="300">Hochauflösend (300)</option></select>` +
    `</div>` +
    `<button type="submit" class="btn-primary">` +
    `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>` +
    `PDF erzeugen` +
    `</button>` +
    `</form>`
  );
}

export function wirePrintForm(
  root: HTMLElement,
  map: OLMap,
  project: ServiceProject,
): void {
  const form = root.querySelector('#print-form') as HTMLFormElement | null;
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const layout = (root.querySelector('#print-layout') as HTMLSelectElement).value;
    const dpi = (root.querySelector('#print-dpi') as HTMLSelectElement).value;
    const view = map.getView();
    const extent = view.calculateExtent(map.getSize() ?? [800, 600]);

    const visible = map
      .getAllLayers()
      .filter((l) => l.get('planportal-layer') && l.getVisible())
      .map((l) => l.get('layer-id'))
      .filter(Boolean);

    const params = new URLSearchParams({
      MAP: `${project.slug}/${project.slug}.qgz`,
      SERVICE: 'WMS',
      VERSION: '1.3.0',
      REQUEST: 'GetPrint',
      FORMAT: 'pdf',
      TEMPLATE: layout,
      CRS: project.crs,
      DPI: dpi,
      LAYERS: visible.join(','),
      'map0:EXTENT': extent.join(','),
      'map0:LAYERS': visible.join(','),
    });
    const url = `${__WEB_QGIS_BASE__}/ows/?${params.toString()}`;
    window.open(url, '_blank', 'noopener');
  });
}
