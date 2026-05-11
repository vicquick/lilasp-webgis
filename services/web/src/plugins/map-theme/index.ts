// Map-theme switcher — mirrors QGIS <visibility-presets>.
// The list is rendered as a <select>; switching dispatches setVisible() per layer
// on the underlying OL map. This is the QGIS Desktop ↔ webGIS fidelity contract.

import type { Map as OLMap } from 'ol';
import LayerGroup from 'ol/layer/Group';
import type { ServiceProject } from '../../lib/services-loader';

export function mountMapThemeSwitcher(
  container: HTMLElement,
  map: OLMap,
  project: ServiceProject,
): void {
  if (!project.themes.length) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML =
    '<h2>Karten-Themen</h2>' +
    '<select id="map-theme-select">' +
    project.themes.map((t) => `<option value="${t.name}">${t.name}</option>`).join('') +
    '</select>';

  const select = container.querySelector('#map-theme-select') as HTMLSelectElement;
  select.addEventListener('change', () => {
    const themeName = select.value;
    const theme = project.themes.find((t) => t.name === themeName);
    if (!theme) return;
    const visible = new Set(theme.visible_layer_ids.map((id) => `${project.slug}__${id}`));
    walkLayers(map, (layer) => {
      const id = layer.get('id') as string | undefined;
      if (id) layer.setVisible(visible.has(id));
    });
  });
}

function walkLayers(map: OLMap, fn: (l: any) => void): void {
  map.getLayers().forEach(function visit(l) {
    if (l instanceof LayerGroup) {
      l.getLayers().forEach(visit);
    } else {
      fn(l);
    }
  });
}
