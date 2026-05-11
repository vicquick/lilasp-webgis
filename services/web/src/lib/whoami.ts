export interface WhoAmI {
  user: string | null;
  email?: string | null;
  name?: string | null;
  uid?: string | null;
  groups: string[];
  entitlements: string[];
  authenticated: boolean;
}

declare const __WEB_WHOAMI__: string;

export async function fetchWhoAmI(): Promise<WhoAmI | null> {
  // 401 from /whoami is the expected state on basic-auth interim — the
  // auth-gateway only echoes Authentik forward-auth headers, which
  // don't exist before Authentik is wired in. Suppress the 401 noise
  // in the console: only `.ok` responses are parsed; everything else
  // returns null silently.
  try {
    const r = await fetch(__WEB_WHOAMI__, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
    if (!r.ok) return null;
    return (await r.json()) as WhoAmI;
  } catch {
    return null;
  }
}
