// Map-theme dropdown. Wires to the layer-tree to toggle visibility per theme.

import type { ServiceProject } from '../../lib/services-loader';

export function mountMapThemeSelect(
  container: HTMLElement,
  project: ServiceProject,
  onChange: (themeName: string) => void,
): void {
  if (!project.themes.length) {
    container.innerHTML = '';
    return;
  }
  const opts = project.themes
    .map(
      (t) =>
        `<option value="${t.name}">${t.name.replace(/_/g, ' ')} (${t.visible_layer_ids.length})</option>`,
    )
    .join('');
  container.innerHTML =
    `<select class="theme-select" id="map-theme-select">` +
    `<option value="" disabled selected>Thema wählen…</option>` +
    opts +
    `</select>`;
  const select = container.querySelector('#map-theme-select') as HTMLSelectElement;
  select.addEventListener('change', () => {
    if (select.value) onChange(select.value);
  });
}
