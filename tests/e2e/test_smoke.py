from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def app_ctx(tmp_path):
    """Fully-assembled app with a real (temp) server.toml + project config."""
    data_dir = tmp_path / "data"
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    (projects_dir / "test.toml").write_text(
        'key="test"\nname="Test"\n'
        '[kinds.feature]\nlabel="Feature"\nprefix="FEAT"\n'
        '[statuses.proposed]\nlabel="P"\n'
        '[statuses.done]\nlabel="D"\nterminal=true\nrequires_ship=true\n'
        '[[branches]]\nkey="main"\nlabel="Main"\n'
    )
    server_toml = tmp_path / "server.toml"
    server_toml.write_text(
        f'host="127.0.0.1"\nport=8765\napi_token="test-tok"\n'
        f'data_dir="{data_dir.as_posix()}"\n'
        f'projects_dir="{projects_dir.as_posix()}"\n'
        '[[tokens]]\nname="readonly"\ntoken="read-tok"\nscopes=["read"]\n'
        '[[tokens]]\nname="agent"\ntoken="agent-tok"\nscopes=["agent"]\n'
        '[[tokens]]\nname="admin"\ntoken="admin-tok"\nscopes=["admin"]\n'
    )

    from alembic import command
    from alembic.config import Config
    data_dir.mkdir()
    db = data_dir / "tracker.db"
    cfg = Config(str(Path.cwd() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")

    from issuedeck.app import create_app
    app = create_app(server_toml)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t",
    ) as c:
        yield c


async def test_healthz(app_ctx):
    r = await app_ctx.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_readyz(app_ctx):
    r = await app_ctx.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "version": "0.1.0", "projects": 1}


async def test_root_redirects_to_dashboard(app_ctx):
    r = await app_ctx.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard/"


async def test_dashboard_requires_login_cookie(app_ctx):
    r = await app_ctx.get("/dashboard/test", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/dashboard/login?next=")

    r = await app_ctx.post(
        "/dashboard/login",
        data={"token": "wrong", "next": "/dashboard/test"},
    )
    assert r.status_code == 401

    r = await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "https://example.test/"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard/"

    r = await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "/dashboard/test"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "issuedeck_dashboard_session" in r.headers["set-cookie"]

    r = await app_ctx.get("/dashboard/test")
    assert r.status_code == 200
    assert "Test" in r.text


async def test_dashboard_login_requires_admin_token(app_ctx):
    r = await app_ctx.post(
        "/dashboard/login",
        data={"token": "agent-tok", "next": "/dashboard/test"},
    )
    assert r.status_code == 401

    r = await app_ctx.post(
        "/dashboard/login",
        data={"token": "admin-tok", "next": "/dashboard/test"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "issuedeck_dashboard_session" in r.headers["set-cookie"]


async def test_dashboard_list_has_work_queues(app_ctx):
    await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "/dashboard/test/list"},
        follow_redirects=False,
    )

    r = await app_ctx.get("/dashboard/test/list?view=blocked")
    assert r.status_code == 200
    assert "Recently touched" in r.text
    assert "Blocked" in r.text
    assert "Ready to ship" in r.text


async def test_dashboard_can_save_and_select_project_filters(app_ctx):
    await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "/dashboard/test/list"},
        follow_redirects=False,
    )

    r = await app_ctx.post(
        "/dashboard/test/saved-filters",
        data={
            "name": "Feature queue",
            "view": "recent",
            "kind": "feature",
            "status": "proposed",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard/test/list?saved_filter=feature-queue"

    r = await app_ctx.get(r.headers["location"])
    assert r.status_code == 200
    assert "Feature queue" in r.text
    assert "saved_filter=feature-queue" in r.text
    assert 'name="kind" value="feature"' in r.text


async def test_dashboard_language_switch_sets_cookie(app_ctx):
    await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "/dashboard/test/list"},
        follow_redirects=False,
    )

    r = await app_ctx.get("/dashboard/test/list?view=blocked")
    assert r.status_code == 200
    assert '<html lang="en"' in r.text
    assert "Recently touched" in r.text
    assert "Blocked" in r.text
    assert "Ready to ship" in r.text
    assert ">List</h1>" in r.text
    assert "Filter" in r.text
    assert ">列表</h1>" not in r.text
    assert "筛选" not in r.text

    r = await app_ctx.post(
        "/dashboard/language",
        data={"lang": "zh-CN", "next": "/dashboard/test/list?view=blocked"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard/test/list?view=blocked"
    assert "issuedeck_lang=zh-CN" in r.headers["set-cookie"]

    r = await app_ctx.get("/dashboard/test/list?view=blocked")
    assert r.status_code == 200
    assert '<html lang="zh-CN"' in r.text
    assert ">列表</h1>" in r.text
    assert "筛选" in r.text
    assert "被阻塞" in r.text

    r = await app_ctx.post(
        "/dashboard/language",
        data={"lang": "en", "next": "/dashboard/test/list?view=blocked"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "issuedeck_lang=en" in r.headers["set-cookie"]

    r = await app_ctx.get("/dashboard/test/list?view=blocked")
    assert r.status_code == 200
    assert '<html lang="en"' in r.text
    assert ">List</h1>" in r.text
    assert ">列表</h1>" not in r.text
    assert "筛选" not in r.text


async def test_dashboard_can_create_project(app_ctx):
    await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "/dashboard/projects-new"},
        follow_redirects=False,
    )

    r = await app_ctx.post(
        "/dashboard/projects-new",
        data={
            "key": "demo",
            "name": "Demo Project",
            "description": "Fake project for screenshots.",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard/demo"

    r = await app_ctx.get("/dashboard/demo")
    assert r.status_code == 200
    assert "Demo Project" in r.text


async def test_full_lifecycle_requires_token(app_ctx):
    r = await app_ctx.post("/api/v1/projects/test/items",
                           json={"kind": "feature", "title": "x"})
    assert r.status_code == 401

    h = {"Authorization": "Bearer test-tok"}

    r = await app_ctx.post("/api/v1/projects/test/items",
                           headers=h, json={
                               "kind": "feature",
                               "title": "Hello",
                               "external_links": [
                                   {
                                       "link_type": "github_pr",
                                       "label": "PR #99",
                                       "url": "https://github.com/example/repo/pull/99",
                                   }
                               ],
                           })
    assert r.status_code == 201, r.text
    assert r.json()["local_id"] == "FEAT-0001"
    assert r.json()["external_links"][0]["label"] == "PR #99"

    r = await app_ctx.post(
        "/api/v1/projects/test/items/FEAT-0001/ship",
        headers=h, json={"branch": "main", "version": "0.1.0", "commits": ["abc"]},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    r = await app_ctx.get("/api/v1/projects/test/items", headers=h)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["external_links"][0]["url"].endswith("/pull/99")

    await app_ctx.post(
        "/dashboard/login",
        data={"token": "test-tok", "next": "/dashboard/test/items/FEAT-0001"},
        follow_redirects=False,
    )
    r = await app_ctx.get("/dashboard/test/items/FEAT-0001")
    assert r.status_code == 200
    assert "External links" in r.text
    assert "PR #99" in r.text
    assert "https://github.com/example/repo/pull/99" in r.text

    r = await app_ctx.get("/api/v1/projects", headers=h)
    assert r.status_code == 200
    assert r.json()["projects"][0]["item_count"] == 1


async def test_scoped_tokens_allow_and_deny_requests(app_ctx):
    read_headers = {"Authorization": "Bearer read-tok"}
    agent_headers = {"Authorization": "Bearer agent-tok"}

    r = await app_ctx.get("/api/v1/projects", headers=read_headers)
    assert r.status_code == 200

    r = await app_ctx.post(
        "/api/v1/projects/test/items",
        headers=read_headers,
        json={"kind": "feature", "title": "Read token cannot write"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"

    r = await app_ctx.post(
        "/api/v1/projects/test/items",
        headers=agent_headers,
        json={"kind": "feature", "title": "Agent token can write"},
    )
    assert r.status_code == 201, r.text

    r = await app_ctx.get("/dashboard/test", headers=agent_headers)
    assert r.status_code == 403
