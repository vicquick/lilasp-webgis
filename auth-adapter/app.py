"""lilasp-webgis auth adapter.

Replaces qwc-auth-service. Validates credentials against QFieldCloud,
maps QFC project roles to QWC2 JWT groups, issues signed JWT cookie.

Endpoints expected by QWC2:
  GET  /auth/login     — HTML login form (with ?url= return param)
  POST /auth/login     — process form, set JWT cookie, redirect to ?url
  POST /auth/logout    — clear cookie, redirect
  GET  /auth/userinfo  — JSON user info from JWT
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from urllib.parse import urlparse

import jwt
import requests
from flask import Flask, jsonify, make_response, redirect, render_template, request

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/auth/static")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

QFC_BASE = os.environ["QFC_BASE_URL"].rstrip("/")
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
JWT_EXPIRY = int(os.environ.get("JWT_EXPIRY_HOURS", 8)) * 3600
COOKIE_NAME = "jwt"
COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

# QFC project name → QWC2 theme slug
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

WRITE_ROLES = {"owner", "manager", "admin", "editor"}


def _safe_return_url(url: str | None) -> str:
    """Only allow relative URLs or same-host URLs, to prevent open redirect."""
    if not url:
        return "/"
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != request.host:
        return "/"
    # Keep path + query + fragment
    return parsed.path + (f"?{parsed.query}" if parsed.query else "") + (f"#{parsed.fragment}" if parsed.fragment else "") or "/"


def _qfc_login(username: str, password: str) -> str | None:
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


def _wants_json() -> bool:
    """Detect XHR/JSON client vs browser navigation."""
    accept = request.headers.get("Accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    if request.is_json:
        return True
    return False


@app.route("/auth/login", methods=["GET"])
def login_page():
    return_url = _safe_return_url(request.args.get("url"))
    if _wants_json():
        return jsonify({"login_url": f"/auth/login?url={return_url}"}), 200
    token = request.cookies.get(COOKIE_NAME)
    if token and _decode_jwt(token):
        return redirect(return_url or "/")
    return render_template("login.html", error=None, return_url=return_url)


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) if request.is_json else None
    if data is None:
        data = request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    return_url = _safe_return_url(data.get("url"))

    if not username or not password:
        if _wants_json():
            return jsonify({"error": "username and password required"}), 400
        return render_template("login.html", error="Benutzername und Passwort erforderlich.", return_url=return_url), 400

    qfc_token = _qfc_login(username, password)
    if not qfc_token:
        log.warning("Login failed for user: %s", username)
        if _wants_json():
            return jsonify({"error": "Authentication failed"}), 401
        return render_template("login.html", error="Anmeldung fehlgeschlagen. Zugangsdaten prüfen.", return_url=return_url), 401

    projects = _qfc_projects(qfc_token)
    groups = _build_groups(projects)
    jwt_token, csrf = _issue_jwt(username, groups)

    log.info("Login OK: %s groups=%s", username, groups)

    if _wants_json():
        resp = make_response(
            jsonify({"username": username, "csrf_token": csrf, "groups": groups})
        )
    else:
        resp = make_response(redirect(return_url or "/"))
    resp.set_cookie(
        COOKIE_NAME,
        jwt_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Lax",
        max_age=JWT_EXPIRY,
        path="/",
    )
    return resp


@app.route("/auth/logout", methods=["POST", "GET"])
def logout():
    return_url = _safe_return_url(request.args.get("url"))
    if _wants_json():
        resp = make_response(jsonify({"message": "logged out"}))
    else:
        resp = make_response(redirect(return_url or "/"))
    resp.delete_cookie(COOKIE_NAME, path="/")
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
