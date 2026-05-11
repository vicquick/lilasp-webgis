// Map-theme dropdown. Wires to the layer-tree to toggle visibility per theme.

import type { ServiceProject } from '../../lib/services-loader';

function escapeHtml(s: string): string {
  return s.replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' })[c]!);
}

/** Pretty-print a QGIS theme name: "A1_Benotung" → "A1 · Benotung". */
function prettify(name: string): string {
  return name.replace(/[_\s]+/g, ' · ').trim();
}

export function mountMapThemeSelect(
  container: HTMLElement,
  project: ServiceProject,
  onChange: (themeName: string) => void,
  defaultThemeName: string | null = null,
): void {
  if (!project.themes.length) {
    container.innerHTML = '';
    return;
  }
  const opts = project.themes
    .map((t) => {
      const selected = t.name === defaultThemeName ? ' selected' : '';
      const label = `${escapeHtml(prettify(t.name))} (${t.visible_layer_ids.length})`;
      return `<option value="${escapeHtml(t.name)}"${selected}>${label}</option>`;
    })
    .join('');
  const placeholder = defaultThemeName
    ? ''
    : '<option value="" disabled selected>Thema wählen…</option>';
  container.innerHTML =
    `<select class="theme-select" id="map-theme-select" aria-label="Karten-Thema">` +
    placeholder +
    opts +
    `</select>`;
  const select = container.querySelector('#map-theme-select') as HTMLSelectElement;
  select.addEventListener('change', () => {
    if (select.value) onChange(select.value);
  });
}
