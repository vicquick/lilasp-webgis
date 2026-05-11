import './styles.css';
import { registerCRS } from './lib/crs';
import { fetchWhoAmI } from './lib/whoami';
import { loadServices, type ServiceProject } from './lib/services-loader';
import { createProjectMap, type BuiltMap } from './lib/masterportal-bridge';
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

const inspectorApi = {
  open(title: string, html: string): void {
    $('#inspector-title').textContent = title;
    $('#inspector-body').innerHTML = html;
    $('#root').setAttribute('data-inspector', 'true');
  },
  close(): void {
    $('#root').setAttribute('data-inspector', 'false');
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

  const builtMap = createProjectMap('map', project);
  state.builtMap = builtMap;

  const status: StatusReporter = {
    set(kind, text) {
      const pill = $('#status-pill');
      pill.innerHTML = `<span class="dot dot--${kind}"></span><span class="status-text">${text}</span>`;
    },
  };
  mountLayerTree($('#layer-tree'), builtMap, project, $('#layers-count'), status);

  $('#layers-default').onclick = () => setAllLayers($('#layer-tree'), builtMap, project, 'qgis-default');
  $('#layers-none').onclick = () => setAllLayers($('#layer-tree'), builtMap, project, 'none');
  mountMapThemeSelect($('#map-themes'), project, (themeName) =>
    applyTheme($('#layer-tree'), builtMap, project, themeName),
  );
  mountIdentify(builtMap.map, project, inspectorApi);
  mountMapControls({
    builtMap,
    zoomEl: $('#map-tools-zoom'),
    rightEl: $('#map-tools-right'),
    onOpenPrint: showInspectorPrint,
  });
  mountCoordsReadout(builtMap.map, $('#readout-coords'), project.crs);

  mountProjectPicker($('#project-picker'), state.projects, slug, $('#projects-count'));

  history.replaceState(null, '', `?project=${encodeURIComponent(slug)}`);
}

async function boot(): Promise<void> {
  registerCRS();

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
