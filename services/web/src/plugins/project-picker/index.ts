// Project picker — card list in the left sidebar.

import type { ServiceProject } from '../../lib/services-loader';

function escapeHtml(s: string): string {
  return s.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c]!);
}

export function mountProjectPicker(
  container: HTMLElement,
  projects: ServiceProject[],
  currentSlug: string | null,
  countEl?: HTMLElement | null,
): void {
  if (countEl) countEl.textContent = `${projects.length}`;
  if (!projects.length) {
    container.innerHTML = '<div class="layer-tree__empty">Keine Projekte. Lege ein .qgz unter /srv/gis/&lt;slug&gt;/ ab.</div>';
    return;
  }
  container.innerHTML = projects
    .map((p) => {
      const layerCount = p.layers.filter((l) => l.geom_type !== 'No geometry').length;
      return (
        `<button type="button" class="project-card" data-slug="${escapeHtml(p.slug)}" data-active="${p.slug === currentSlug}">` +
          `<span class="project-card__title">${escapeHtml(p.title)}</span>` +
          `<span class="project-card__meta">${layerCount} Layer · ${p.themes.length} Themen · ${p.print_layouts.length} Drucklayouts</span>` +
        `</button>`
      );
    })
    .join('');
  container.querySelectorAll<HTMLButtonElement>('button[data-slug]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const slug = btn.dataset.slug!;
      window.dispatchEvent(new CustomEvent('webgis:project', { detail: { slug } }));
    });
  });
}
