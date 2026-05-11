"""Planportal auth-gateway — whoami sidecar.

Reads the Authentik forward-auth response headers Traefik injects on every
request and echoes them as JSON for the SPA. Groups are split on `|`
(Authentik's separator — splitting on `,` is the most common bug).
"""
from __future__ import annotations

from flask import Flask, jsonify, request

app = Flask(__name__)


def _split_groups(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [g for g in raw.split("|") if g]


@app.get("/whoami")
def whoami():
    user = request.headers.get("X-Authentik-Username")
    if not user:
        return jsonify(error="not authenticated"), 401
    return jsonify(
        user=user,
        email=request.headers.get("X-Authentik-Email"),
        name=request.headers.get("X-Authentik-Name"),
        uid=request.headers.get("X-Authentik-Uid"),
        groups=_split_groups(request.headers.get("X-Authentik-Groups")),
        entitlements=_split_groups(request.headers.get("X-Authentik-Entitlements")),
    )


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
