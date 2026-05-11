// Inline SVG icons, lucide-inspired. Each fn returns a snippet of
// `width=18 height=18 viewBox=0 0 24 24 stroke=currentColor` etc. so
// the icon picks up the parent's color via `currentColor`.

export const ICON_SIZE = 18;

function svg(path: string): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${ICON_SIZE}" height="${ICON_SIZE}" ` +
    `viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ` +
    `stroke-linecap="round" stroke-linejoin="round">${path}</svg>`
  );
}

export const icons = {
  plus:    () => svg('<path d="M12 5v14M5 12h14"/>'),
  minus:   () => svg('<path d="M5 12h14"/>'),
  home:    () => svg('<path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/>'),
  layers:  () => svg('<path d="M12 2l10 6-10 6L2 8z"/><path d="M2 14l10 6 10-6"/>'),
  locate:  () => svg('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>'),
  search:  () => svg('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>'),
  info:    () => svg('<circle cx="12" cy="12" r="9"/><path d="M12 10v6M12 7v.01"/>'),
  table:   () => svg('<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 10h18M9 4v16"/>'),
  print:   () => svg('<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="9" rx="1"/><path d="M6 18h12v4H6z"/>'),
  share:   () => svg('<circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8.6 13.5l6.8 3M15.4 7.5l-6.8 3"/>'),
  globe:   () => svg('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/>'),
  close:   () => svg('<path d="M18 6L6 18M6 6l12 12"/>'),
  ruler:   () => svg('<path d="M21 6L18 3 3 18l3 3z"/><path d="M7 14l2 2M10 11l2 2M13 8l2 2M16 5l2 2"/>'),
  download:() => svg('<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/>'),
  eye:     () => svg('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
};
