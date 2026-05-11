// Custom map overlay controls (zoom, fit, locate, basemap switcher,
// identify mode, print). Replaces OL's built-in zoom buttons with
// LILASp-styled SVG icons.

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
    button({ icon: icons.plus(), title: 'Hineinzoomen', onClick: () => map.getView().setZoom((map.getView().getZoom() ?? 6) + 1) }),
    button({ icon: icons.minus(), title: 'Herauszoomen', onClick: () => map.getView().setZoom((map.getView().getZoom() ?? 6) - 1) }),
    button({ icon: icons.home(), title: 'Auf Projektausdehnung zoomen', onClick: () => builtMap.fitToProject() }),
  );

  let basemapKey: BasemapKey = 'carto';
  const cycleBasemap = (btn: HTMLButtonElement) => {
    const order: BasemapKey[] = ['carto', 'osm', 'esriSat'];
    basemapKey = order[(order.indexOf(basemapKey) + 1) % order.length] as BasemapKey;
    builtMap.setBasemap(basemapKey);
    btn.title = `Basiskarte: ${basemapKey}`;
  };

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
    button({ icon: icons.layers(), title: 'Basiskarte wechseln', onClick: cycleBasemap }),
    button({ icon: icons.locate(), title: 'Mein Standort', onClick: locate }),
    button({ icon: icons.print(), title: 'Drucken (PDF)', onClick: onOpenPrint }),
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
