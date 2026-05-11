export interface WhoAmI {
  user: string;
  email?: string;
  name?: string;
  uid?: string;
  groups: string[];
  entitlements: string[];
}

declare const __WEB_WHOAMI__: string;

export async function fetchWhoAmI(): Promise<WhoAmI | null> {
  try {
    const r = await fetch(__WEB_WHOAMI__, { credentials: 'include' });
    if (!r.ok) return null;
    return (await r.json()) as WhoAmI;
  } catch {
    return null;
  }
}
