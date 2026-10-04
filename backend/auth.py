"""
Auth gate: GitHub OAuth sign-in → app-issued JWTs in httpOnly cookies.

Flow
    /auth/login     state + PKCE verifier in a short-lived signed cookie → redirect to GitHub
    /auth/callback  verify state, exchange code, fetch the GitHub user, check ALLOWED_USERS,
                    then set tv_access (15 min) + tv_refresh (7 days) + tv_csrf
    /auth/refresh   rotate both tokens (needs the refresh cookie + X-CSRF-Token header)
    /auth/logout    clear the cookies
    /auth/me        who am I (401 when signed out)

Every /api/* route except /api/health requires a valid access token; non-GET
/api requests also need the CSRF double-submit header. Socket.IO connections
are checked with socket_user() in app.py.

The gate fails closed: if auth is not configured and AUTH_DISABLED=1 is not
set, /api/* answers 503 instead of serving data unauthenticated.
"""
import base64
import hashlib
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import jwt
import requests
from flask import Blueprint, current_app, g, jsonify, redirect, request

log = logging.getLogger("auth")

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

ISSUER      = "tradeview"
AUDIENCE    = "tradeview-web"
ACCESS_TTL  = 15 * 60
REFRESH_TTL = 7 * 24 * 3600
OAUTH_TTL   = 10 * 60
LEEWAY      = 30

ACCESS_COOKIE  = "tv_access"
REFRESH_COOKIE = "tv_refresh"
CSRF_COOKIE    = "tv_csrf"
OAUTH_COOKIE   = "tv_oauth"
CSRF_HEADER    = "X-CSRF-Token"

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL     = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL      = "https://api.github.com/user"

PUBLIC_API_PATHS = {"/api/health"}


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AuthConfig:
    disabled: bool = False
    secret: str = ""
    client_id: str = ""
    client_secret: str = ""
    allowed: frozenset = frozenset()
    public_url: str = ""
    cookie_secure: bool = True
    token_version: str = "1"

    @classmethod
    def from_env(cls) -> "AuthConfig":
        return cls(
            disabled=os.getenv("AUTH_DISABLED", "") == "1",
            secret=os.getenv("JWT_SECRET", ""),
            client_id=os.getenv("GITHUB_CLIENT_ID", ""),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
            allowed=frozenset(u.strip().lower() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()),
            public_url=os.getenv("PUBLIC_URL", "").rstrip("/"),
            cookie_secure=os.getenv("COOKIE_SECURE", "1") != "0",
            token_version=os.getenv("TOKEN_VERSION", "1"),
        )

    @property
    def missing(self) -> list[str]:
        problems = []
        if len(self.secret) < 32:
            problems.append("JWT_SECRET (min 32 chars)")
        if not self.client_id:
            problems.append("GITHUB_CLIENT_ID")
        if not self.client_secret:
            problems.append("GITHUB_CLIENT_SECRET")
        if not self.allowed:
            problems.append("ALLOWED_USERS")
        return problems

    @property
    def configured(self) -> bool:
        return not self.missing


def _cfg() -> AuthConfig:
    return current_app.config["AUTH"]


# ── Tokens ────────────────────────────────────────────────────────────────────

def issue_token(cfg: AuthConfig, typ: str, sub: str, ttl: int, **extra) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": sub, "typ": typ, "ver": cfg.token_version,
        "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex, **extra,
    }
    return jwt.encode(claims, cfg.secret, algorithm="HS256")


def verify_token(cfg: AuthConfig, token: str | None, typ: str) -> dict | None:
    """Decoded claims if the token is valid and of the expected type, else None."""
    if not token or not cfg.secret:
        return None
    try:
        claims = jwt.decode(
            token, cfg.secret, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
            leeway=LEEWAY, options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != typ or claims.get("ver") != cfg.token_version:
        return None
    return claims


def socket_user() -> str | None:
    """Username for the current Socket.IO handshake/event, or None if not signed in."""
    cfg = _cfg()
    if cfg.disabled:
        return "dev"
    claims = verify_token(cfg, request.cookies.get(ACCESS_COOKIE), "access")
    return claims["sub"] if claims else None


# ── Cookies ───────────────────────────────────────────────────────────────────

def _set_cookie(resp, cfg, name, value, max_age, path="/", httponly=True, samesite="Strict"):
    resp.set_cookie(name, value, max_age=max_age, path=path, httponly=httponly,
                    secure=cfg.cookie_secure, samesite=samesite)


def _start_session(resp, cfg: AuthConfig, sub: str, uid, avatar: str | None):
    extra = {"uid": uid, "avt": avatar}
    _set_cookie(resp, cfg, ACCESS_COOKIE, issue_token(cfg, "access", sub, ACCESS_TTL, **extra), ACCESS_TTL)
    _set_cookie(resp, cfg, REFRESH_COOKIE, issue_token(cfg, "refresh", sub, REFRESH_TTL, **extra),
                REFRESH_TTL, path="/auth")
    # Readable by JS on purpose: the SPA echoes it back in the X-CSRF-Token header.
    _set_cookie(resp, cfg, CSRF_COOKIE, secrets.token_urlsafe(24), REFRESH_TTL, httponly=False)


def _end_session(resp):
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path="/auth")
    resp.delete_cookie(CSRF_COOKIE, path="/")


def _csrf_ok() -> bool:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    return bool(cookie) and secrets.compare_digest(cookie, header)


def _callback_url(cfg: AuthConfig) -> str:
    base = cfg.public_url or request.host_url.rstrip("/")
    return f"{base}/auth/callback"


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ── Gate ──────────────────────────────────────────────────────────────────────

def gate():
    """before_request hook: protect /api/* (except PUBLIC_API_PATHS)."""
    path = request.path
    if not path.startswith("/api/") or path in PUBLIC_API_PATHS or request.method == "OPTIONS":
        return None
    cfg = _cfg()
    if cfg.disabled:
        g.user = "dev"
        return None
    if not cfg.configured:
        return jsonify({"error": "auth not configured"}), 503
    claims = verify_token(cfg, request.cookies.get(ACCESS_COOKIE), "access")
    if claims is None:
        return jsonify({"error": "unauthorized"}), 401
    if request.method != "GET" and not _csrf_ok():
        return jsonify({"error": "csrf check failed"}), 403
    g.user = claims["sub"]
    return None


def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if not current_app.debug:
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; connect-src 'self'; "
            "img-src 'self' https://avatars.githubusercontent.com data:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
    return resp


def init_auth(app, cfg: AuthConfig | None = None):
    cfg = cfg or AuthConfig.from_env()
    app.config["AUTH"] = cfg
    app.register_blueprint(auth_bp)
    app.before_request(gate)
    app.after_request(security_headers)
    if cfg.disabled:
        log.warning("AUTH_DISABLED=1 — every request is treated as signed in. Local development only!")
    elif not cfg.configured:
        log.error("Auth not configured (missing: %s) — /api/* will answer 503.", ", ".join(cfg.missing))
    else:
        log.info("Auth enabled for GitHub users: %s", ", ".join(sorted(cfg.allowed)))


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.get("/login")
def login():
    cfg = _cfg()
    if cfg.disabled:
        return redirect("/")
    if not cfg.configured:
        return jsonify({"error": "auth not configured"}), 503

    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)          # 64 chars, within PKCE's 43–128
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": _callback_url(cfg),
        "scope": "read:user",
        "state": state,
        "code_challenge": _pkce_challenge(verifier),
        "code_challenge_method": "S256",
        "allow_signup": "false",
    }
    resp = redirect(f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}")
    oauth = issue_token(cfg, "oauth", "pending", OAUTH_TTL, state=state, verifier=verifier)
    # Lax, not Strict: it has to survive the top-level redirect back from github.com.
    _set_cookie(resp, cfg, OAUTH_COOKIE, oauth, OAUTH_TTL, path="/auth", samesite="Lax")
    return resp


@auth_bp.get("/callback")
def callback():
    cfg = _cfg()
    if not cfg.configured:
        return jsonify({"error": "auth not configured"}), 503

    def _fail(reason: str):
        resp = redirect(f"/?auth_error={reason}")
        resp.delete_cookie(OAUTH_COOKIE, path="/auth")
        return resp

    if request.args.get("error"):
        return _fail("denied")

    pending = verify_token(cfg, request.cookies.get(OAUTH_COOKIE), "oauth")
    state = request.args.get("state", "")
    if pending is None or not secrets.compare_digest(pending.get("state", ""), state):
        return jsonify({"error": "invalid or expired sign-in state"}), 400

    code = request.args.get("code", "")
    if not code:
        return _fail("github")
    try:
        token_res = requests.post(GITHUB_TOKEN_URL, timeout=10, headers={"Accept": "application/json"}, data={
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "code": code,
            "redirect_uri": _callback_url(cfg),
            "code_verifier": pending["verifier"],
        })
        gh_token = token_res.json().get("access_token")
        if not gh_token:
            log.warning("GitHub token exchange failed: %s", token_res.json().get("error"))
            return _fail("github")
        user_res = requests.get(GITHUB_USER_URL, timeout=10, headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        })
        user_res.raise_for_status()
        user = user_res.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("GitHub sign-in error: %s", e)
        return _fail("github")

    login_name = user.get("login", "")
    if login_name.lower() not in cfg.allowed:
        log.warning("Sign-in refused for GitHub user %r (not in ALLOWED_USERS)", login_name)
        return _fail("not_allowed")

    log.info("Signed in: %s", login_name)
    resp = redirect("/")
    resp.delete_cookie(OAUTH_COOKIE, path="/auth")
    _start_session(resp, cfg, login_name, user.get("id"), user.get("avatar_url"))
    return resp


@auth_bp.post("/refresh")
def refresh():
    cfg = _cfg()
    if cfg.disabled:
        return jsonify({"login": "dev"})
    if not _csrf_ok():
        return jsonify({"error": "csrf check failed"}), 403
    claims = verify_token(cfg, request.cookies.get(REFRESH_COOKIE), "refresh")
    if claims is None:
        resp = jsonify({"error": "unauthorized"})
        _end_session(resp)
        return resp, 401
    resp = jsonify({"login": claims["sub"]})
    _start_session(resp, cfg, claims["sub"], claims.get("uid"), claims.get("avt"))
    return resp


@auth_bp.post("/logout")
def logout():
    if not _cfg().disabled and not _csrf_ok():
        return jsonify({"error": "csrf check failed"}), 403
    resp = jsonify({"ok": True})
    _end_session(resp)
    return resp


@auth_bp.get("/me")
def me():
    cfg = _cfg()
    if cfg.disabled:
        return jsonify({"login": "dev", "avatar_url": None, "auth_disabled": True})
    claims = verify_token(cfg, request.cookies.get(ACCESS_COOKIE), "access")
    if claims is None:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"login": claims["sub"], "avatar_url": claims.get("avt"), "auth_disabled": False})
