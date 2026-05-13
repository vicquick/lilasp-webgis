"""WebGIS auth-gateway.

Two responsibilities:

1. **Forward-auth** (`/auth/forward`): Traefik fires this before every
   public request. We respond `200` + identity headers if the user
   carries a valid signed cookie, otherwise `302 → /auth/login` so the
   browser shows our styled login page instead of the grey basic-auth
   dialog.

2. **Login flow** (`/auth/login` GET/POST, `/auth/logout`): renders a
   small Flask-based HTML form that matches the WebGIS palette.
   Credentials are validated against bcrypt hashes supplied via the
   `WEBGIS_AUTH_USERS` env var (`user1:$2a$...|user2:$2a$...` —
   `|`-separated, `:`-split so bcrypt's own `$` characters don't need
   special escaping).

3. **Whoami** (`/whoami`): kept for the SPA topbar — now reads the
   `X-Authentik-*` headers that the Traefik forward-auth response
   injects via `authResponseHeaders` (we re-use the Authentik header
   names so swapping in real Authentik later is a one-line config flip).

Cookie format: `<b64url(user)>.<exp_unix>.<b64url(hmac_sha256)>` —
small, stateless, no database. Secret comes from `WEBGIS_AUTH_SECRET`
(refusal to start without it). Cookie is HttpOnly + Secure + SameSite=Lax.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import os
import time
import urllib.parse
from html import escape as h
from typing import Optional

import bcrypt
from flask import Flask, jsonify, make_response, redirect, request

app = Flask(__name__)


# ─── config ─────────────────────────────────────────────────────────

def _env_required(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"env var {name} is required")
    return v


def _users() -> dict[str, bytes]:
    """Parse WEBGIS_AUTH_USERS into {user: bcrypt_hash_bytes}."""
    raw = os.environ.get("WEBGIS_AUTH_USERS", "").strip()
    if not raw:
        return {}
    out: dict[str, bytes] = {}
    for entry in raw.split("|"):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        # split() on first colon — bcrypt hashes contain `:`-free digits
        # but the password itself never appears, so first split is safe.
        user, _, h_str = entry.partition(":")
        if user and h_str.startswith("$2"):
            out[user] = h_str.encode()
    return out


SECRET = _env_required("WEBGIS_AUTH_SECRET").encode()
COOKIE_NAME = os.environ.get("WEBGIS_AUTH_COOKIE", "webgis_auth")
COOKIE_TTL_S = int(os.environ.get("WEBGIS_AUTH_TTL_DAYS", "7")) * 86400
USERS = _users()


# ─── cookie sign / verify ───────────────────────────────────────────

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(user: str, exp: int) -> str:
    payload = f"{_b64e(user.encode())}.{exp}".encode()
    sig = hmac.new(SECRET, payload, hashlib.sha256).digest()
    return f"{payload.decode()}.{_b64e(sig)}"


def _verify(cookie: str) -> Optional[str]:
    try:
        u_b64, exp_str, sig_b64 = cookie.split(".")
        exp = int(exp_str)
    except (ValueError, AttributeError):
        return None
    if exp < int(time.time()):
        return None
    payload = f"{u_b64}.{exp}".encode()
    expected = hmac.new(SECRET, payload, hashlib.sha256).digest()
    try:
        got = _b64d(sig_b64)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(expected, got):
        return None
    try:
        return _b64d(u_b64).decode()
    except (ValueError, UnicodeDecodeError):
        return None


def _current_user() -> Optional[str]:
    c = request.cookies.get(COOKIE_NAME)
    return _verify(c) if c else None


# ─── routes ─────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/whoami")
def whoami():
    """Read identity from headers (set by Traefik forwardAuth) and echo as JSON.

    We continue to expose the `X-Authentik-*` header names so that
    plugging real Authentik in later is a label flip on Traefik, no
    SPA changes needed.
    """
    user = request.headers.get("X-Authentik-Username") or _current_user()
    return jsonify(
        user=user,
        email=request.headers.get("X-Authentik-Email"),
        name=request.headers.get("X-Authentik-Name") or user,
        uid=request.headers.get("X-Authentik-Uid"),
        groups=[g for g in (request.headers.get("X-Authentik-Groups") or "").split("|") if g],
        entitlements=[g for g in (request.headers.get("X-Authentik-Entitlements") or "").split("|") if g],
        authenticated=bool(user),
    )


# ─── forward-auth (Traefik calls this on every protected request) ───

@app.get("/auth/forward")
def forward():
    """Return 200 if authenticated, else 302 → login.

    Traefik passes the original request's URI via `X-Forwarded-Uri`.
    Anything under `/auth/` MUST pass through unauthenticated so the
    login page (and its assets) can be reached.
    """
    uri = request.headers.get("X-Forwarded-Uri", "/")
    if uri.startswith("/auth/") or uri == "/healthz":
        return ("", 200)

    user = _current_user()
    if user:
        # Forward identity to the upstream via response headers; Traefik
        # picks these up if listed in `authResponseHeaders`.
        resp = make_response("", 200)
        resp.headers["X-Authentik-Username"] = user
        resp.headers["X-Authentik-Name"] = user
        return resp

    # Build an ABSOLUTE Location URL pointing at the public host.
    # Traefik's forwardAuth resolves relative Locations against the
    # auth-server URL (http://auth-gateway:5000/...), which the user's
    # browser cannot reach. We must emit `https://webgis.lilasp.de/...`
    # so the redirect lands on the styled login page.
    host = request.headers.get("X-Forwarded-Host", request.host)
    proto = request.headers.get("X-Forwarded-Proto", "https")
    next_url = f"{proto}://{host}{uri}"
    login_url = (
        f"{proto}://{host}/auth/login?next=" + urllib.parse.quote(next_url, safe="")
    )
    return redirect(login_url, code=302)


# ─── login page ─────────────────────────────────────────────────────

def _is_safe_next(target: str) -> bool:
    """Avoid open redirects: only allow same-host targets."""
    if not target:
        return False
    parsed = urllib.parse.urlparse(target)
    if not parsed.netloc:
        return target.startswith("/")
    host = request.headers.get("X-Forwarded-Host", request.host)
    return parsed.netloc == host


_PAGE_CSS = """
:root {
  color-scheme: light dark;
  --teal:        #0f766e;
  --teal-hi:     #115e59;
  --teal-soft:   rgba(15, 118, 110, 0.10);
  --teal-line:   rgba(15, 118, 110, 0.28);
  --bg:          #fbfaf7;
  --bg-soft:     #f3f1ec;
  --surface:     #ffffff;
  --surface-hi:  #f8f7f2;
  --border:      rgba(20, 30, 35, 0.10);
  --border-soft: rgba(20, 30, 35, 0.06);
  --text:        #0f1c1f;
  --text-dim:    #4f6064;
  --text-mute:   #84908f;
  --danger:      #b3413a;
  --shadow:      0 8px 30px rgba(15,28,31,0.08);
  --shadow-lg:   0 24px 60px rgba(15,28,31,0.10);
  --radius:      11px;
  --radius-lg:   18px;
  --font-sans:   'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-serif:  'Fraunces', 'Times New Roman', serif;
  --font-mono:   'JetBrains Mono', 'SF Mono', 'Menlo', monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --teal:        #2dd4bf;
    --teal-hi:     #5eead4;
    --teal-soft:   rgba(45, 212, 191, 0.14);
    --teal-line:   rgba(45, 212, 191, 0.32);
    --bg:          #0c1416;
    --bg-soft:     #111c1f;
    --surface:     #152125;
    --surface-hi:  #1c2b30;
    --border:      rgba(255, 255, 255, 0.07);
    --border-soft: rgba(255, 255, 255, 0.04);
    --text:        #ecf6f5;
    --text-dim:    #9eb1b1;
    --text-mute:   #6b8181;
    --shadow:      0 8px 30px rgba(0,0,0,0.45);
    --shadow-lg:   0 24px 60px rgba(0,0,0,0.55);
  }
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0; height: 100%;
  background: var(--bg); color: var(--text);
  font: 14px/1.55 var(--font-sans);
  font-feature-settings: 'ss01', 'cv11', 'tnum';
  -webkit-font-smoothing: antialiased;
}
body {
  min-height: 100dvh;
  display: grid; place-items: center;
  padding: 24px;
  background:
    radial-gradient(70% 50% at 30% 25%, var(--teal-soft) 0, transparent 60%),
    radial-gradient(60% 60% at 80% 80%, color-mix(in oklab, var(--teal) 8%, transparent) 0, transparent 70%),
    var(--bg);
}
.card {
  width: 100%; max-width: 380px;
  padding: 36px 32px 28px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  position: relative;
}
.brand {
  display: flex; align-items: baseline; gap: 9px;
  margin-bottom: 4px;
  color: var(--teal);
}
.brand svg {
  width: 28px; height: 28px;
  filter: drop-shadow(0 0 8px var(--teal-soft));
}
.brand__name {
  font: 600 24px/1 var(--font-serif);
  letter-spacing: -0.02em;
  color: var(--text);
}
.brand__tag {
  font: 500 11px/1 var(--font-sans);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-mute);
}
h1 {
  margin: 28px 0 8px;
  font: 500 18px/1.3 var(--font-sans);
  color: var(--text);
  letter-spacing: -0.005em;
}
.hint {
  font-size: 13px; color: var(--text-dim);
  margin: 0 0 22px;
}
form { display: flex; flex-direction: column; gap: 14px; }
.field {
  display: flex; flex-direction: column; gap: 6px;
}
.field label {
  font: 500 11px/1 var(--font-sans);
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-mute);
}
.field input {
  appearance: none;
  width: 100%;
  padding: 12px 14px;
  background: var(--surface-hi);
  color: var(--text);
  font: 500 14.5px/1.2 var(--font-sans);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color 140ms ease, background 140ms ease, box-shadow 140ms ease;
}
.field input:hover { border-color: var(--teal-line); }
.field input:focus {
  outline: 0; border-color: var(--teal);
  box-shadow: 0 0 0 3px var(--teal-soft);
  background: var(--surface);
}
.btn {
  margin-top: 6px;
  padding: 13px 16px;
  background: var(--teal); color: white;
  font: 600 14px/1 var(--font-sans);
  letter-spacing: 0.01em;
  border: 0; border-radius: var(--radius);
  cursor: pointer;
  transition: background 140ms ease, transform 120ms ease;
}
.btn:hover { background: var(--teal-hi); }
.btn:active { transform: scale(0.98); }
.error {
  display: flex; align-items: center; gap: 8px;
  margin: -4px 0 4px;
  padding: 10px 12px;
  background: color-mix(in oklab, var(--danger) 14%, transparent);
  color: var(--danger);
  border: 1px solid color-mix(in oklab, var(--danger) 30%, transparent);
  border-radius: var(--radius);
  font-size: 13px;
}
.foot {
  margin-top: 22px;
  font: 11px/1.4 var(--font-mono);
  letter-spacing: 0.04em;
  color: var(--text-mute);
  text-align: center;
}
.foot a { color: var(--text-dim); text-decoration: none; }
.foot a:hover { color: var(--teal); }
"""


def _page(error: str | None, prefill_user: str, next_q: str) -> str:
    err_html = ""
    if error:
        err_html = (
            f'<div class="error" role="alert">'
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17v.01"/></svg>'
            f'{h(error)}</div>'
        )
    next_html = f'<input type="hidden" name="next" value="{h(next_q)}" />' if next_q else ""
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#fbfaf7" />
  <title>WebGIS · Anmelden</title>
  <link rel="preconnect" href="https://rsms.me" crossorigin />
  <link rel="stylesheet" href="https://rsms.me/inter/inter.css" />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500&display=swap" />
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%230f766e'%3E%3Cpath d='M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6L12 2z'/%3E%3C/svg%3E" />
  <style>{_PAGE_CSS}</style>
</head>
<body>
  <main class="card">
    <div class="brand">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6L12 2z"/>
      </svg>
      <span class="brand__name">WebGIS</span>
      <span class="brand__tag">LILASp</span>
    </div>
    <h1>Bei WebGIS anmelden</h1>
    <p class="hint">Bitte gib deine Zugangsdaten ein. Bei Problemen wende dich an deinen LILASp-Admin.</p>
    {err_html}
    <form method="post" action="/auth/login" autocomplete="on" novalidate>
      {next_html}
      <div class="field">
        <label for="user">Benutzername</label>
        <input id="user" name="user" type="text"
               value="{h(prefill_user)}"
               autocomplete="username" autocapitalize="off"
               autocorrect="off" spellcheck="false"
               required autofocus />
      </div>
      <div class="field">
        <label for="pw">Passwort</label>
        <input id="pw" name="password" type="password"
               autocomplete="current-password" required />
      </div>
      <button class="btn" type="submit">Anmelden</button>
    </form>
    <div class="foot">webgis.lilasp.de · gesichert · v1</div>
  </main>
</body>
</html>"""


@app.get("/auth/login")
def login_get():
    if _current_user():
        nxt = request.args.get("next", "/")
        return redirect(nxt if _is_safe_next(nxt) else "/", code=302)
    err = request.args.get("err")
    user = request.args.get("user", "")
    next_q = request.args.get("next", "")
    body = _page(err or None, user, next_q)
    resp = make_response(body, 200)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/auth/login")
def login_post():
    user = (request.form.get("user") or "").strip()
    password = (request.form.get("password") or "").encode()
    next_q = request.form.get("next", "")

    hashed = USERS.get(user)
    if not (user and hashed and password and bcrypt.checkpw(password, hashed)):
        # Generic message - no user-vs-pass disambiguation.
        return redirect(
            "/auth/login?err=" + urllib.parse.quote("Benutzername oder Passwort falsch.")
            + ("&user=" + urllib.parse.quote(user) if user else "")
            + ("&next=" + urllib.parse.quote(next_q) if next_q else ""),
            code=303,
        )

    exp = int(time.time()) + COOKIE_TTL_S
    cookie = _sign(user, exp)
    target = next_q if _is_safe_next(next_q) else "/"
    resp = make_response(redirect(target, code=303))
    resp.set_cookie(
        COOKIE_NAME, cookie,
        max_age=COOKIE_TTL_S,
        httponly=True, secure=True, samesite="Lax",
        path="/",
    )
    return resp


@app.get("/auth/logout")
def logout():
    resp = make_response(redirect("/auth/login", code=302))
    resp.set_cookie(COOKIE_NAME, "", max_age=0, httponly=True, secure=True, samesite="Lax", path="/")
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
