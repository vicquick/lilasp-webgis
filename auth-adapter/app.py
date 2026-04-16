"""lilasp-webgis auth adapter.

Replaces qwc-auth-service. Validates credentials against QFieldCloud,
maps QFC project roles to QWC2 JWT groups, issues signed JWT cookie.

Endpoints expected by qwc-services:
  POST /auth/login     — log in, set jwt cookie
  POST /auth/logout    — clear jwt cookie
  GET  /auth/userinfo  — return user info from jwt
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from functools import wraps

import jwt
import requests
from flask import Flask, jsonify, make_response, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

QFC_BASE = os.environ["QFC_BASE_URL"].rstrip("/")
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
JWT_EXPIRY = int(os.environ.get("JWT_EXPIRY_HOURS", 8)) * 3600
COOKIE_NAME = "jwt"
COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

# QFC project name → QWC2 theme slug
# Add new projects here as they go live in WebGIS
PROJECT_THEME_MAP: dict[str, str] = {
    "WIE_Spielplaetze": "wiesbaden",
    "CUX_Spielplaetze": "cuxhaven",
    "Cuxhaven_Spielplaetze": "cuxhaven",
    "FFM_Naturerlebnisprofile": "frankfurt_nep",
    "FFM_Orte": "frankfurt_orte",
    "FFM_Plaetze": "frankfurt_plaetze",
    "FFM_Wege": "frankfurt_wege",
    "Schnelsen_HCS_Baeume": "schnelsen_baeume",
}

# QFC roles that grant write access in QWC2
WRITE_ROLES = {"owner", "manager", "admin", "editor"}


def _qfc_login(username: str, password: str) -> str | None:
    """Authenticate against QFC, return QFC token or None."""
    try:
        r = requests.post(
            f"{QFC_BASE}/auth/login/",
            json={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("token")
    except requests.RequestException as e:
        log.error("QFC login error: %s", e)
    return None


def _qfc_projects(qfc_token: str) -> list[dict]:
    """Fetch all projects visible to this user, with their role."""
    try:
        r = requests.get(
            f"{QFC_BASE}/projects/",
            headers={"Authorization": f"Token {qfc_token}"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException as e:
        log.error("QFC projects error: %s", e)
    return []


def _build_groups(projects: list[dict]) -> list[str]:
    """Map QFC project roles to QWC2 group names.

    Format: {theme}_{access}  where access = 'reader' | 'editor'
    """
    groups: list[str] = []
    for proj in projects:
        name = proj.get("name", "")
        role = proj.get("user_role") or ""
        theme = PROJECT_THEME_MAP.get(name)
        if not theme or not role:
            continue
        access = "editor" if role in WRITE_ROLES else "reader"
        groups.append(f"{theme}_{access}")
    return groups


def _issue_jwt(username: str, groups: list[str]) -> tuple[str, str]:
    """Return (jwt_token, csrf_token)."""
    csrf = secrets.token_hex(16)
    now = int(time.time())
    payload = {
        "sub": username,
        "username": username,
        "groups": groups,
        "csrf_token": csrf,
        "iat": now,
        "exp": now + JWT_EXPIRY,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    return token, csrf


def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None


@app.route("/auth/login", methods=["GET"])
def login_page():
    """QWC2 expects a redirect-able login page for unauthenticated access."""
    return jsonify({"login_url": "/auth/login"}), 200


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or request.form.get("username", "")).strip()
    password = data.get("password") or request.form.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    qfc_token = _qfc_login(username, password)
    if not qfc_token:
        log.warning("Login failed for user: %s", username)
        return jsonify({"error": "Authentication failed"}), 401

    projects = _qfc_projects(qfc_token)
    groups = _build_groups(projects)
    jwt_token, csrf = _issue_jwt(username, groups)

    log.info("Login OK: %s groups=%s", username, groups)

    resp = make_response(
        jsonify({"username": username, "csrf_token": csrf, "groups": groups})
    )
    resp.set_cookie(
        COOKIE_NAME,
        jwt_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Strict",
        max_age=JWT_EXPIRY,
    )
    return resp


@app.route("/auth/logout", methods=["POST", "GET"])
def logout():
    resp = make_response(jsonify({"message": "logged out"}))
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.route("/auth/userinfo", methods=["GET"])
def userinfo():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify({"error": "not authenticated"}), 401
    payload = _decode_jwt(token)
    if not payload:
        return jsonify({"error": "invalid token"}), 401
    return jsonify({
        "username": payload.get("username"),
        "groups": payload.get("groups", []),
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
