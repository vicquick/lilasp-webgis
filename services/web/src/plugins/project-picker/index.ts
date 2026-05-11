// Project picker — minimal grid of buttons from services.json. Selecting one
// emits a `planportal:project` event which app.ts listens for.

import type { ServiceProject } from '../../lib/services-loader';

export function mountProjectPicker(
  container: HTMLElement,
  projects: ServiceProject[],
  currentSlug: string | null,
): void {
  container.innerHTML =
    '<h2>Projekte</h2>' +
    projects
      .map(
        (p) =>
          `<button class="project-picker__item${p.slug === currentSlug ? ' project-picker__item--active' : ''}" data-slug="${p.slug}">` +
          `<strong>${p.title}</strong><br/><small>${p.layers.length} Layer · ${p.themes.length} Themen</small>` +
          `</button>`,
      )
      .join('');
  container.querySelectorAll<HTMLButtonElement>('button[data-slug]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const slug = btn.dataset.slug as string;
      window.dispatchEvent(new CustomEvent('planportal:project', { detail: { slug } }));
    });
  });
}
