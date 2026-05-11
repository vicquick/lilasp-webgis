# Authentik setup checklist (manual, post-deploy)

Authentik can't be created via the MCP `service` tool today (ADR-0006).
Follow these UI steps after Planportal's first deploy succeeds.

## 1. Create the service in Coolify

1. Open `coolify.lilasp.de` → project **Authentik** (`a4kwss4k0s844g8ws0ss088s`) → environment **production**.
2. **+ Add new resource → Service → Authentik** (the template).
   If the template isn't available, paste `authentik-compose.yml` from
   this directory into a Docker Compose service.
3. Set FQDN: `https://auth.lilasp.de`.
4. Set env vars from the secrets generated at deploy time
   (stashed at `/tmp/planportal-secrets.env` on the workserver, mode 600):
   - `AUTHENTIK_POSTGRES_PASSWORD`
   - `AUTHENTIK_SECRET_KEY`
   - `AUTHENTIK_BOOTSTRAP_PASSWORD`
   - `AUTHENTIK_BOOTSTRAP_TOKEN`
5. Deploy.

## 2. First login

- Browse to `https://auth.lilasp.de/if/flow/initial-setup/`.
- Log in as `akadmin` with the bootstrap password.
- Change the password and disable bootstrap env vars (`AUTHENTIK_BOOTSTRAP_*`)
  on the Coolify service after first login.

## 3. Provider + Application for Planportal

1. **Applications → Providers → Create → Proxy Provider**:
   - Name: `planportal-proxy`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Mode: **Forward auth (single application)**
   - External host: `https://webgis.lilasp.de`
   - Save.
2. **Applications → Applications → Create**:
   - Name: `Planportal`
   - Slug: `planportal`
   - Provider: `planportal-proxy`
   - Launch URL: `https://webgis.lilasp.de`
   - Save.
3. **Outpost** — confirm the embedded outpost is set in the provider
   binding (System → Outposts → `authentik Embedded Outpost`).

## 4. Groups + role mapping

Create groups that map to project roles:

| Group | Planportal role | Notes |
|---|---|---|
| `planportal-admin` | full admin | all projects |
| `cuxhaven-editor` | editor | Cuxhaven |
| `cuxhaven-viewer` | viewer | Cuxhaven |
| `frankfurt-…` | ... | per-project |

Bind groups to the `Planportal` application via Policy → Group binding.

## 5. Swap Planportal middleware

Once steps 1-4 are done, edit the repo's `docker-compose.yml` on the
`web` service: change the router middleware list from

```
traefik.http.routers.planportal-web.middlewares=planportal-sec@docker,planportal-rl@docker,planportal-auth@docker
```

to

```
traefik.http.routers.planportal-web.middlewares=planportal-sec@docker,planportal-rl@docker,authentik-auth@docker
```

… and delete the `planportal-auth.basicauth.*` lines plus the
`PLANPORTAL_BASIC_AUTH_USERS` Coolify env var.

Commit, push, redeploy. The basic-auth prompt should be replaced by the
Authentik login flow.

## 6. Sidecar `/whoami`

Planportal's `auth-gateway` container reads `X-Authentik-*` response
headers Traefik injects and echoes them to the SPA at `/whoami`. The
SPA splits `X-Authentik-Groups` on `|` (not `,` — Authentik's
separator); the split is implemented in `services/auth-gateway/app.py`
and `services/web/src/lib/whoami.ts`.

## 7. Rotate bootstrap secrets

After a working Authentik admin login:
- Unset `AUTHENTIK_BOOTSTRAP_PASSWORD` and `AUTHENTIK_BOOTSTRAP_TOKEN`
  on the Coolify service.
- Delete `/tmp/planportal-secrets.env` from the workserver.
