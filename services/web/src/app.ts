import 'ol/ol.css';

import { registerCRS } from './lib/crs';
import { fetchWhoAmI } from './lib/whoami';
import { loadServices, type ServiceProject } from './lib/services-loader';
import { createProjectMap } from './lib/masterportal-bridge';
import { mountProjectPicker } from './plugins/project-picker';
import { mountMapThemeSwitcher } from './plugins/map-theme';
import { mountGetPrintLauncher } from './plugins/getprint';

interface AppState {
  projects: ServiceProject[];
  currentSlug: string | null;
}

const state: AppState = { projects: [], currentSlug: null };


async function selectProject(slug: string): Promise<void> {
  const project = state.projects.find((p) => p.slug === slug);
  if (!project) return;
  state.currentSlug = slug;

  document.getElementById('project-title')!.textContent = project.title;
  document.getElementById('map')!.innerHTML = '';
  const map = await createProjectMap({ containerId: 'map', project });

  mountMapThemeSwitcher(document.getElementById('map-themes')!, map, project);
  mountGetPrintLauncher(document.getElementById('inspector')!, map, project);
  mountProjectPicker(
    document.getElementById('project-picker')!,
    state.projects,
    state.currentSlug,
  );

  history.replaceState(null, '', `?project=${encodeURIComponent(slug)}`);
}


async function boot(): Promise<void> {
  registerCRS();

  const who = await fetchWhoAmI();
  document.getElementById('userinfo')!.textContent = who
    ? `${who.user} (${who.groups.length} Gruppen)`
    : 'nicht angemeldet';

  const payload = await loadServices();
  state.projects = payload.projects;

  mountProjectPicker(document.getElementById('project-picker')!, state.projects, null);

  window.addEventListener('planportal:project', (e) => {
    const slug = (e as CustomEvent<{ slug: string }>).detail.slug;
    void selectProject(slug);
  });

  const initial = new URL(window.location.href).searchParams.get('project')
    ?? state.projects[0]?.slug
    ?? null;
  if (initial) {
    await selectProject(initial);
  }
}

void boot();
