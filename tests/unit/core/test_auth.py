from fastapi import FastAPI
from fastapi.testclient import TestClient

from issuedeck.core.auth import (
    DASHBOARD_SESSION_COOKIE,
    BearerTokenCredential,
    BearerTokenMiddleware,
    make_dashboard_session_cookie,
)


def _app(
    token: str | None = None,
    tokens: list[BearerTokenCredential] | None = None,
) -> FastAPI:
    app = FastAPI()
    kwargs = {
        "exempt_paths": ("/healthz", "/dashboard/login"),
        "dashboard_paths": ("/dashboard",),
    }
    if tokens is not None:
        kwargs["tokens"] = tokens
    else:
        kwargs["token"] = token
    app.add_middleware(BearerTokenMiddleware, **kwargs)

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.get("/api/v1/ping")
    def ping():
        return {"pong": True}

    @app.post("/api/v1/ping")
    def write_ping():
        return {"written": True}

    @app.get("/dashboard/login")
    def login():
        return {"login": True}

    @app.get("/dashboard/ping")
    def dashboard_ping():
        return {"dashboard": True}

    @app.post("/dashboard/ping")
    def dashboard_post():
        return {"dashboard": True}

    return app


def _scoped_app() -> FastAPI:
    return _app(tokens=[
        BearerTokenCredential(
            name="read",
            token="read-token",
            scopes=frozenset({"read"}),
        ),
        BearerTokenCredential(
            name="agent",
            token="agent-token",
            scopes=frozenset({"agent"}),
        ),
        BearerTokenCredential(
            name="admin",
            token="admin-token",
            scopes=frozenset({"admin"}),
        ),
    ])


def test_healthz_is_exempt():
    c = TestClient(_app("secret"))
    r = c.get("/healthz")
    assert r.status_code == 200


def test_missing_token_returns_401():
    c = TestClient(_app("secret"))
    r = c.get("/api/v1/ping")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_wrong_token_returns_401():
    c = TestClient(_app("secret"))
    r = c.get("/api/v1/ping", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "invalid bearer token"


def test_correct_token_passes():
    c = TestClient(_app("secret"))
    r = c.get("/api/v1/ping", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    assert r.json() == {"pong": True}


def test_dashboard_get_redirects_to_login_without_session():
    c = TestClient(_app("secret"))
    r = c.get("/dashboard/ping?tab=list", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard/login?next=%2Fdashboard%2Fping%3Ftab%3Dlist"


def test_dashboard_post_returns_401_without_session():
    c = TestClient(_app("secret"))
    r = c.post("/dashboard/ping")
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "missing dashboard session"


def test_dashboard_accepts_session_cookie():
    c = TestClient(_app("secret"))
    c.cookies.set(DASHBOARD_SESSION_COOKIE, make_dashboard_session_cookie("secret"))
    r = c.get("/dashboard/ping")
    assert r.status_code == 200
    assert r.json() == {"dashboard": True}


def test_dashboard_accepts_bearer_token():
    c = TestClient(_app("secret"))
    r = c.get("/dashboard/ping", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    assert r.json() == {"dashboard": True}


def test_read_token_allows_get_and_denies_write():
    c = TestClient(_scoped_app())
    h = {"Authorization": "Bearer read-token"}
    assert c.get("/api/v1/ping", headers=h).status_code == 200

    r = c.post("/api/v1/ping", headers=h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_agent_token_allows_api_write_but_not_dashboard():
    c = TestClient(_scoped_app())
    h = {"Authorization": "Bearer agent-token"}
    assert c.get("/api/v1/ping", headers=h).status_code == 200
    assert c.post("/api/v1/ping", headers=h).status_code == 200

    r = c.get("/dashboard/ping", headers=h)
    assert r.status_code == 403


def test_admin_token_allows_api_and_dashboard():
    c = TestClient(_scoped_app())
    h = {"Authorization": "Bearer admin-token"}
    assert c.post("/api/v1/ping", headers=h).status_code == 200
    assert c.get("/dashboard/ping", headers=h).status_code == 200


def test_dashboard_cookie_accepts_any_admin_token():
    c = TestClient(_scoped_app())
    c.cookies.set(
        DASHBOARD_SESSION_COOKIE,
        make_dashboard_session_cookie("admin-token"),
    )
    r = c.get("/dashboard/ping")
    assert r.status_code == 200
