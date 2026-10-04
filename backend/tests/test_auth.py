import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

import app as app_module
import auth
from auth import AuthConfig, issue_token

SECRET = "x" * 48
CFG = AuthConfig(secret=SECRET, client_id="cid", client_secret="csecret",
                 allowed=frozenset({"nettenz"}), public_url="https://tv.example",
                 cookie_secure=False, token_version="1")


@pytest.fixture
def client(monkeypatch, daily_bars):
    monkeypatch.setattr(app_module.ds, "get_bars", lambda symbol, tf, limit=500: daily_bars.tail(limit))
    monkeypatch.setitem(app_module.app.config, "AUTH", CFG)
    return app_module.app.test_client()


def _sign_in(client, sub="netteNz", **overrides):
    token = issue_token(overrides.pop("cfg", CFG), overrides.pop("typ", "access"), sub,
                        overrides.pop("ttl", 900), uid=1, avt=None)
    client.set_cookie(auth.ACCESS_COOKIE, token)
    return token


def _forge(claims, key=SECRET, alg="HS256"):
    base = {"iss": auth.ISSUER, "aud": auth.AUDIENCE, "sub": "netteNz", "typ": "access", "ver": "1",
            "iat": int(time.time()), "exp": int(time.time()) + 900}
    base.update(claims)
    return jwt.encode(base, key, algorithm=alg)


# ── Gate ──────────────────────────────────────────────────────────────────────

def test_api_requires_token(client):
    assert client.get("/api/chart/SPY?limit=5").status_code == 401
    assert client.get("/api/health").status_code == 200          # stays public


def test_valid_access_token_passes(client):
    _sign_in(client)
    assert client.get("/api/chart/SPY?limit=5").status_code == 200


@pytest.mark.parametrize("token", [
    _forge({"exp": int(time.time()) - 3600}),                    # expired
    _forge({"aud": "someone-else"}),                             # wrong audience
    _forge({"iss": "evil"}),                                     # wrong issuer
    _forge({"typ": "refresh"}),                                  # refresh used as access
    _forge({"ver": "0"}),                                        # revoked by TOKEN_VERSION bump
    _forge({}, key="y" * 48),                                    # wrong key
    jwt.encode({"sub": "netteNz", "typ": "access"}, None, algorithm="none"),   # alg=none
])
def test_bad_tokens_rejected(client, token):
    client.set_cookie(auth.ACCESS_COOKIE, token)
    assert client.get("/api/chart/SPY?limit=5").status_code == 401


def test_unconfigured_auth_fails_closed(client, monkeypatch):
    monkeypatch.setitem(app_module.app.config, "AUTH", AuthConfig())
    assert client.get("/api/chart/SPY?limit=5").status_code == 503


def test_security_headers(client):
    res = client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]


# ── Refresh / logout / me ─────────────────────────────────────────────────────

def test_refresh_needs_csrf_and_rotates(client):
    client.set_cookie(auth.REFRESH_COOKIE, issue_token(CFG, "refresh", "netteNz", 3600, uid=1, avt=None), path="/auth")
    client.set_cookie(auth.CSRF_COOKIE, "csrf123")
    assert client.post("/auth/refresh").status_code == 403
    res = client.post("/auth/refresh", headers={"X-CSRF-Token": "csrf123"})
    assert res.status_code == 200
    cookies = res.headers.getlist("Set-Cookie")
    assert any(c.startswith("tv_access=") and "HttpOnly" in c and "SameSite=Strict" in c for c in cookies)
    assert any(c.startswith("tv_refresh=") and "Path=/auth" in c for c in cookies)


def test_refresh_rejects_access_token(client):
    client.set_cookie(auth.REFRESH_COOKIE, issue_token(CFG, "access", "netteNz", 3600), path="/auth")
    client.set_cookie(auth.CSRF_COOKIE, "c")
    assert client.post("/auth/refresh", headers={"X-CSRF-Token": "c"}).status_code == 401


def test_me_and_logout(client):
    assert client.get("/auth/me").status_code == 401
    _sign_in(client)
    assert client.get("/auth/me").get_json()["login"] == "netteNz"
    client.set_cookie(auth.CSRF_COOKIE, "c")
    res = client.post("/auth/logout", headers={"X-CSRF-Token": "c"})
    assert res.status_code == 200
    assert any(c.startswith("tv_access=;") for c in res.headers.getlist("Set-Cookie"))


# ── OAuth flow ────────────────────────────────────────────────────────────────

def _start_login(client):
    res = client.get("/auth/login")
    assert res.status_code == 302
    query = parse_qs(urlparse(res.headers["Location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://tv.example/auth/callback"]
    return query["state"][0]


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


def _mock_github(monkeypatch, login):
    seen = {}

    def fake_post(url, **kw):
        seen["verifier"] = kw["data"]["code_verifier"]
        return _Resp({"access_token": "gho_test"})

    monkeypatch.setattr(auth.requests, "post", fake_post)
    monkeypatch.setattr(auth.requests, "get", lambda url, **kw: _Resp({"login": login, "id": 7, "avatar_url": "a"}))
    return seen


def test_callback_rejects_state_mismatch(client, monkeypatch):
    _mock_github(monkeypatch, "netteNz")
    _start_login(client)
    assert client.get("/auth/callback?code=abc&state=forged").status_code == 400


def test_callback_signs_in_allowed_user(client, monkeypatch):
    seen = _mock_github(monkeypatch, "netteNz")
    state = _start_login(client)
    res = client.get(f"/auth/callback?code=abc&state={state}")
    assert res.status_code == 302 and res.headers["Location"] == "/"
    assert len(seen["verifier"]) >= 43
    assert client.get_cookie(auth.ACCESS_COOKIE) is not None
    assert client.get("/api/chart/SPY?limit=5").status_code == 200


def test_callback_refuses_other_users(client, monkeypatch):
    _mock_github(monkeypatch, "someone-else")
    state = _start_login(client)
    res = client.get(f"/auth/callback?code=abc&state={state}")
    assert res.headers["Location"] == "/?auth_error=not_allowed"
    assert client.get_cookie(auth.ACCESS_COOKIE) is None


# ── Socket.IO ─────────────────────────────────────────────────────────────────

def test_socket_requires_token(client):
    sio = app_module.socketio.test_client(app_module.app, flask_test_client=client)
    assert not sio.is_connected()
    _sign_in(client)
    sio = app_module.socketio.test_client(app_module.app, flask_test_client=client)
    assert sio.is_connected()
    sio.disconnect()
