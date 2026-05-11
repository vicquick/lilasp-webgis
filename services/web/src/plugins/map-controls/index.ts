// Custom map overlay controls (zoom, fit, locate, basemap cycle,
// print). Replaces OL's built-in zoom buttons with on-brand SVG icons.

import type { Map as OLMap } from 'ol';
import { fromLonLat, transform } from 'ol/proj';
import { icons } from '../../lib/icons';
import type { BasemapKey, BuiltMap } from '../../lib/masterportal-bridge';

interface ToolButton {
  icon: string;
  title: string;
  onClick: (btn: HTMLButtonElement) => void;
  pressed?: boolean;
}

function button(cfg: ToolButton): HTMLButtonElement {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'map-tools__btn';
  b.innerHTML = cfg.icon;
  b.title = cfg.title;
  b.setAttribute('aria-label', cfg.title);
  if (cfg.pressed) b.setAttribute('aria-pressed', 'true');
  b.addEventListener('click', () => cfg.onClick(b));
  return b;
}

export interface MapControlsOptions {
  builtMap: BuiltMap;
  zoomEl: HTMLElement;
  rightEl: HTMLElement;
  onOpenPrint: () => void;
}

export function mountMapControls({ builtMap, zoomEl, rightEl, onOpenPrint }: MapControlsOptions): void {
  const { map } = builtMap;
  zoomEl.replaceChildren(
    button({ icon: icons.plus(),  title: 'Hineinzoomen',          onClick: () => map.getView().setZoom((map.getView().getZoom() ?? 6) + 1) }),
    button({ icon: icons.minus(), title: 'Herauszoomen',          onClick: () => map.getView().setZoom((map.getView().getZoom() ?? 6) - 1) }),
    button({ icon: icons.home(),  title: 'Auf Projektausdehnung zoomen', onClick: () => builtMap.fitToProject() }),
  );

  // Cycle: off → carto → cartoDark → osm → esriSat → off …
  // "off" lives in the cycle because the project brief is "themes
  // own the canvas; the basemap is opt-in scaffolding."
  const order: (BasemapKey | null)[] = [null, 'carto', 'cartoDark', 'osm', 'esriSat'];
  const labelOf = (k: BasemapKey | null) =>
    k === null ? 'aus' : { carto: 'CARTO', cartoDark: 'CARTO Dark', osm: 'OSM', esriSat: 'Satellit' }[k];

  const basemapBtn = button({
    icon: icons.layers(),
    title: `Basiskarte: ${labelOf(builtMap.getBasemap())}`,
    onClick: (btn) => {
      const cur = builtMap.getBasemap();
      const idx = order.indexOf(cur);
      const next = order[(idx + 1) % order.length] ?? null;
      builtMap.setBasemap(next);
      btn.title = `Basiskarte: ${labelOf(next)}`;
      btn.setAttribute('aria-pressed', next === null ? 'false' : 'true');
    },
    pressed: builtMap.getBasemap() !== null,
  });

  const locate = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      const view = map.getView();
      const projCode = view.getProjection().getCode();
      const coord = transform([pos.coords.longitude, pos.coords.latitude], 'EPSG:4326', projCode);
      view.animate({ center: coord, zoom: 16, duration: 600 });
    });
  };

  rightEl.replaceChildren(
    basemapBtn,
    button({ icon: icons.locate(), title: 'Mein Standort', onClick: locate }),
    button({ icon: icons.print(),  title: 'Drucken (PDF)', onClick: onOpenPrint }),
  );
}

export function mountCoordsReadout(
  map: OLMap,
  readoutEl: HTMLElement,
  crs: string,
): void {
  map.on('pointermove', (evt) => {
    const x = evt.coordinate[0] ?? 0;
    const y = evt.coordinate[1] ?? 0;
    readoutEl.textContent = `${x.toFixed(1)} · ${y.toFixed(1)}  ${crs}`;
  });
  readoutEl.textContent = `— · —  ${crs}`;
}

// Suppress unused-import warning in tsc strict mode
export const _unused = fromLonLat;
