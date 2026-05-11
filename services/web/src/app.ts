import './styles.css';
import { registerCRS } from './lib/crs';
import { fetchWhoAmI } from './lib/whoami';
import { loadServices, type ServiceProject, type ServiceTheme } from './lib/services-loader';
import { createProjectMap, type BuiltMap } from './lib/masterportal-bridge';
import { bootScheme, toggleScheme } from './lib/theme';
import { mountProjectPicker } from './plugins/project-picker';
import { mountMapThemeSelect } from './plugins/map-theme';
import { mountLayerTree, applyTheme, setAllLayers, type StatusReporter } from './plugins/layer-tree';
import { mountIdentify } from './plugins/identify';
import { renderPrintForm, wirePrintForm } from './plugins/getprint';
import { mountMapControls, mountCoordsReadout } from './plugins/map-controls';

interface AppState {
  projects: ServiceProject[];
  current: ServiceProject | null;
  builtMap: BuiltMap | null;
}

const state: AppState = { projects: [], current: null, builtMap: null };

const $ = (sel: string): HTMLElement => document.querySelector(sel) as HTMLElement;

// ─── inspector helpers ─────────────────────────────────────────────

const inspectorApi = {
  open(title: string, html: string): void {
    $('#inspector-title').textContent = title;
    $('#inspector-body').innerHTML = html;
    const root = $('#root');
    root.setAttribute('data-inspector', 'true');
    // On mobile, default to inspector sheet visible when something opens.
    if (matchMedia('(max-width: 760px)').matches) {
      root.setAttribute('data-mobile-panel', 'inspector');
      $('#mobile-backdrop').toggleAttribute('hidden', false);
      $('#mobile-backdrop').setAttribute('data-open', 'true');
    }
  },
  close(): void {
    $('#root').setAttribute('data-inspector', 'false');
    closeMobilePanel();
  },
  setBusy(busy: boolean): void {
    document.body.style.cursor = busy ? 'progress' : '';
  },
};

function showInspectorPrint(): void {
  if (!state.current || !state.builtMap) return;
  inspectorApi.open('Drucken', renderPrintForm(state.current));
  wirePrintForm($('#inspector-body'), state.builtMap.map, state.current);
}

function escapeHtml(s: string): string {
  return s.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c]!);
}

function showProjectInfo(project: ServiceProject): void {
  const renderable = project.layers.filter((l) => l.geom_type !== 'No geometry').length;
  const lookups = project.layers.filter((l) => l.geom_type === 'No geometry').length;
  const bboxText = project.bbox
    ? project.bbox.map((n) => n.toFixed(0)).join(' · ')
    : '— (unbestimmt)';
  inspectorApi.open(
    'Projekt-Info',
    `<dl>
      <div class="feature__row"><dt>Titel</dt><dd>${escapeHtml(project.title)}</dd></div>
      <div class="feature__row"><dt>Slug</dt><dd>${escapeHtml(project.slug)}</dd></div>
      <div class="feature__row"><dt>CRS</dt><dd>${escapeHtml(project.crs)}</dd></div>
      <div class="feature__row"><dt>BBox</dt><dd>${escapeHtml(bboxText)}</dd></div>
      <div class="feature__row"><dt>Render-Layer</dt><dd>${renderable}</dd></div>
      <div class="feature__row"><dt>Lookup-Tabellen</dt><dd>${lookups}</dd></div>
      <div class="feature__row"><dt>Karten-Themen</dt><dd>${project.themes.length}</dd></div>
      <div class="feature__row"><dt>Drucklayouts</dt><dd>${project.print_layouts.length}</dd></div>
    </dl>`,
  );
}

// ─── default-theme picker ──────────────────────────────────────────
//
// Brief: "load the Benotung theme by default". Match case-insensitively
// and prefer the shortest matching name (so "A1_Benotung" wins over
// "A1_Benotung_Nachfrage").

function pickDefaultTheme(themes: ServiceTheme[]): ServiceTheme | null {
  if (!themes.length) return null;
  const candidates = themes
    .filter((t) => /benotung/i.test(t.name))
    .sort((a, b) => a.name.length - b.name.length);
  return candidates[0] ?? null;
}

// ─── mobile sheet wiring ───────────────────────────────────────────

function isMobile(): boolean { return matchMedia('(max-width: 760px)').matches; }

function openMobilePanel(which: 'sidebar' | 'inspector'): void {
  const root = $('#root');
  root.setAttribute('data-mobile-panel', which);
  const bd = $('#mobile-backdrop');
  bd.removeAttribute('hidden');
  bd.setAttribute('data-open', 'true');
}

function closeMobilePanel(): void {
  const root = $('#root');
  root.setAttribute('data-mobile-panel', 'closed');
  const bd = $('#mobile-backdrop');
  bd.setAttribute('data-open', 'false');
  // Hide after transition so it doesn't intercept clicks.
  setTimeout(() => bd.setAttribute('hidden', ''), 260);
}

function wireMobileShell(): void {
  // Show menu button + FAB on small screens.
  const apply = () => {
    const mobile = isMobile();
    const menuBtn = $('#topbar-menu') as HTMLButtonElement;
    menuBtn.toggleAttribute('hidden', !mobile);
    const fab = $('#fab-inspector') as HTMLButtonElement;
    fab.toggleAttribute('hidden', !mobile);
  };
  apply();
  matchMedia('(max-width: 760px)').addEventListener('change', apply);

  $('#topbar-menu').addEventListener('click', () => {
    const cur = $('#root').getAttribute('data-mobile-panel');
    if (cur === 'sidebar') closeMobilePanel();
    else openMobilePanel('sidebar');
  });
  $('#fab-inspector').addEventListener('click', () => {
    if (state.current) showProjectInfo(state.current);
  });
  $('#mobile-backdrop').addEventListener('click', () => {
    closeMobilePanel();
    // Closing inspector should also collapse the data-inspector grid.
    if (isMobile()) inspectorApi.close();
  });
  // Selecting a project on mobile dismisses the sidebar sheet.
  window.addEventListener('webgis:project', () => {
    if (isMobile()) closeMobilePanel();
  });
}

// ─── theme toggle ──────────────────────────────────────────────────

function wireThemeToggle(): void {
  $('#topbar-theme').addEventListener('click', () => toggleScheme());
}

// ─── project lifecycle ─────────────────────────────────────────────

async function selectProject(slug: string): Promise<void> {
  const project = state.projects.find((p) => p.slug === slug);
  if (!project) return;
  state.current = project;

  $('#project-title').textContent = project.title;
  $('#panel-themes').hidden = !project.themes.length;
  $('#panel-layers').hidden = !project.layers.length;

  // Dispose previous map
  if (state.builtMap) {
    state.builtMap.map.setTarget(undefined);
    state.builtMap = null;
  }
  $('#map').innerHTML = '';

  // Brief: basemap OFF by default; the map theme (Benotung) carries
  // the visual weight. User can still toggle a basemap on later.
  const builtMap = createProjectMap('map', project, { basemap: null });
  state.builtMap = builtMap;

  const status: StatusReporter = {
    set(kind, text) {
      const pill = $('#status-pill');
      pill.innerHTML = `<span class="dot dot--${kind}"></span><span class="status-text">${text}</span>`;
    },
  };
  const layerTreeEl = $('#layer-tree');
  mountLayerTree(layerTreeEl, builtMap, project, $('#layers-count'), status);

  $('#layers-default').onclick = () => setAllLayers(layerTreeEl, builtMap, project, 'qgis-default');
  $('#layers-none').onclick = () => setAllLayers(layerTreeEl, builtMap, project, 'none');

  const defaultTheme = pickDefaultTheme(project.themes);
  mountMapThemeSelect($('#map-themes'), project, (themeName) =>
    applyTheme(layerTreeEl, builtMap, project, themeName),
    defaultTheme?.name ?? null,
  );

  // Apply default theme on load so the canvas isn't blank.
  if (defaultTheme) {
    applyTheme(layerTreeEl, builtMap, project, defaultTheme.name);
    $('#theme-hint').textContent = defaultTheme.name;
  } else {
    $('#theme-hint').textContent = '';
  }

  mountIdentify(builtMap.map, project, inspectorApi);
  mountMapControls({
    builtMap,
    zoomEl: $('#map-tools-zoom'),
    rightEl: $('#map-tools-right'),
    onOpenPrint: showInspectorPrint,
  });
  mountCoordsReadout(builtMap.map, $('#readout-coords'), project.crs);

  mountProjectPicker($('#project-picker'), state.projects, slug, $('#projects-count'));

  showProjectInfo(project);

  history.replaceState(null, '', `?project=${encodeURIComponent(slug)}`);
}

async function boot(): Promise<void> {
  bootScheme();
  registerCRS();
  wireMobileShell();
  wireThemeToggle();

  const userEl = $('#userinfo');
  const who = await fetchWhoAmI();
  userEl.textContent = who ? who.user : 'admin';

  let payload;
  try {
    payload = await loadServices();
  } catch (e) {
    document.body.innerHTML = '<pre style="padding:24px;font-family:system-ui">services.json laden fehlgeschlagen: ' + String(e) + '</pre>';
    return;
  }
  state.projects = payload.projects;

  mountProjectPicker($('#project-picker'), state.projects, null, $('#projects-count'));

  window.addEventListener('webgis:project', (e) => {
    const slug = (e as CustomEvent<{ slug: string }>).detail.slug;
    void selectProject(slug);
  });
  // Back-compat with any cached SPA shipping the old event name.
  window.addEventListener('planportal:project', (e) => {
    const slug = (e as CustomEvent<{ slug: string }>).detail.slug;
    void selectProject(slug);
  });

  $('#inspector-close').addEventListener('click', () => inspectorApi.close());

  const initial = new URL(window.location.href).searchParams.get('project') ?? state.projects[0]?.slug ?? null;
  if (initial) {
    await selectProject(initial);
  }
}

void boot();
