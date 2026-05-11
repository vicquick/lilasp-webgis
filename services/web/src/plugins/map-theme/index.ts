// Map-theme picker. Two presentations sharing one click handler:
//   • desktop: classic <select> dropdown (compact, fits the sidebar)
//   • mobile : touch-friendly chip stack so users can scan + tap
// Both live in the same container — CSS hides whichever doesn't fit.

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

  const chips = project.themes
    .map((t) => {
      const active = t.name === defaultThemeName ? 'true' : 'false';
      return (
        `<button type="button" class="theme-chips__btn" data-theme="${escapeHtml(t.name)}" data-active="${active}">` +
          `<span>${escapeHtml(prettify(t.name))}</span>` +
          `<span class="theme-chips__count">${t.visible_layer_ids.length}</span>` +
        `</button>`
      );
    })
    .join('');

  container.innerHTML =
    `<select class="theme-select" id="map-theme-select" aria-label="Karten-Thema">` +
      placeholder +
      opts +
    `</select>` +
    `<div class="theme-chips" role="listbox" aria-label="Karten-Themen">` +
      chips +
    `</div>`;

  const select = container.querySelector('#map-theme-select') as HTMLSelectElement;
  const syncActive = (themeName: string) => {
    container.querySelectorAll<HTMLButtonElement>('.theme-chips__btn').forEach((btn) => {
      btn.setAttribute('data-active', btn.dataset.theme === themeName ? 'true' : 'false');
    });
  };

  select.addEventListener('change', () => {
    if (select.value) {
      onChange(select.value);
      syncActive(select.value);
    }
  });

  container.querySelectorAll<HTMLButtonElement>('.theme-chips__btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const themeName = btn.dataset.theme!;
      select.value = themeName;
      onChange(themeName);
      syncActive(themeName);
    });
  });
}
