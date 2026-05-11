// GetPrint launcher — opens py-qgis-server's GetPrint endpoint in a new tab.
// PDF is rendered server-side using the QGIS project's own print layout
// (project.print_layouts). Zero divergence from QGIS Desktop.

import type { Map as OLMap } from 'ol';
import type { ServiceProject } from '../../lib/services-loader';

declare const __WEB_QGIS_BASE__: string;

export function mountGetPrintLauncher(
  container: HTMLElement,
  map: OLMap,
  project: ServiceProject,
): void {
  if (!project.print_layouts.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML =
    '<h2>Drucken</h2>' +
    '<select id="print-layout">' +
    project.print_layouts.map((l) => `<option value="${l}">${l}</option>`).join('') +
    '</select>' +
    ' <button id="print-go">PDF</button>';

  const select = container.querySelector('#print-layout') as HTMLSelectElement;
  const button = container.querySelector('#print-go') as HTMLButtonElement;
  button.addEventListener('click', () => {
    const layout = select.value;
    const view = map.getView();
    const extent = view.calculateExtent(map.getSize() ?? [800, 600]);
    const params = new URLSearchParams({
      MAP: `file:/srv/gis/${project.slug}/${project.slug}.qgs`,
      SERVICE: 'WMS',
      VERSION: '1.3.0',
      REQUEST: 'GetPrint',
      FORMAT: 'pdf',
      TEMPLATE: layout,
      CRS: project.crs,
      DPI: '150',
      'map0:EXTENT': extent.join(','),
    });
    const url = `${__WEB_QGIS_BASE__}/?${params.toString()}`;
    window.open(url, '_blank', 'noopener');
  });
}
