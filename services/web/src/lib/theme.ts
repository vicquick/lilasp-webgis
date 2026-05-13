// Color-scheme manager. Persists choice in localStorage; defaults to "light".
//
// Two valid values: "dark" | "light". CSS reads them off `<html data-theme="…">`.

export type ColorScheme = 'dark' | 'light';
const STORAGE_KEY = 'webgis.theme';

export function getScheme(): ColorScheme {
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === 'light' || v === 'dark') return v;
  // First visit: light by default. Office daylight + the darker teal
  // accent reads better on the cream background; users who prefer
  // dark can switch via the topbar moon icon.
  return 'light';
}

export function setScheme(scheme: ColorScheme): void {
  document.documentElement.setAttribute('data-theme', scheme);
  document.documentElement.style.colorScheme = scheme;
  localStorage.setItem(STORAGE_KEY, scheme);
  // Re-tint the address-bar on mobile.
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (meta) {
    meta.content = scheme === 'dark' ? '#0c1416' : '#fbfaf7';
  }
}

export function toggleScheme(): ColorScheme {
  const next: ColorScheme = getScheme() === 'dark' ? 'light' : 'dark';
  setScheme(next);
  return next;
}

/** Apply the persisted (or default) scheme as early as possible. */
export function bootScheme(): ColorScheme {
  const s = getScheme();
  setScheme(s);
  return s;
}
