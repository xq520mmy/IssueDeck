import asyncio
import json
import sqlite3
import subprocess
import sys
import zipfile

import pytest

from issuedeck.cli import (
    _build_registry,
    _cmd_bulk_update_items,
    _cmd_create_item,
    _cmd_demo,
    _cmd_export_audit_bundle,
    _cmd_get_item,
    _cmd_import_csv,
    _cmd_import_github_issues,
    _cmd_import_github_url,
    _cmd_import_json,
    _cmd_import_markdown_list,
    _cmd_list_items,
    _cmd_seed_demo,
    _cmd_serve,
    _cmd_update_item,
    _ensure_demo_config,
    _ensure_demo_project_config,
)
from issuedeck.core.config import load_server_config
from issuedeck.core.errors import ConfigError


def test_issuedeck_help_lists_subcommands():
    r = subprocess.run(
        [sys.executable, "-m", "issuedeck", "--help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    for cmd in (
        "demo",
        "serve",
        "migrate",
        "export",
        "export-audit-bundle",
        "seed-demo",
        "create-item",
        "update-item",
        "bulk-update-items",
        "list-items",
        "get-item",
        "import-github-url",
        "import-github-issues",
        "import-markdown-list",
        "import-csv",
        "import-json",
        "mcp",
    ):
        assert cmd in out, f"{cmd} missing from --help"


def test_migrate_help_lists_presets():
    r = subprocess.run(
        [sys.executable, "-m", "issuedeck", "migrate", "--help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    assert "--preset" in out
    assert "github" in out
    assert "linear" in out


def test_ensure_demo_config_writes_missing_config(tmp_path):
    cfg_path = tmp_path / "server.toml"

    assert _ensure_demo_config(cfg_path) is True
    text = cfg_path.read_text(encoding="utf-8")
    assert 'api_token = "issuedeck-local-token"' in text
    assert 'data_dir = "' in text
    assert 'projects_dir = "' in text

    original = text.replace("issuedeck-local-token", "custom-token")
    cfg_path.write_text(original, encoding="utf-8")
    assert _ensure_demo_config(cfg_path) is False
    assert cfg_path.read_text(encoding="utf-8") == original


def test_demo_prepare_creates_config_project_db_and_fake_data(tmp_path, monkeypatch):
    monkeypatch.delenv("ISSUEDECK_API_TOKEN", raising=False)
    monkeypatch.delenv("ISSUEDECK_DATA_DIR", raising=False)
    monkeypatch.delenv("ISSUEDECK_PROJECTS_DIR", raising=False)

    cfg_path = tmp_path / "server.toml"

    rc = _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    assert rc == 0
    assert cfg_path.exists()
    assert (tmp_path / "projects" / "example.toml").exists()
    assert (tmp_path / "data" / "tracker.db").exists()
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        item_count = conn.execute(
            "select count(*) from items where project_key = 'example'"
        ).fetchone()[0]
    assert item_count == 8


def test_serve_runs_database_migrations_before_starting(tmp_path, monkeypatch):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")

    run_calls = []

    def fake_run(app, **kwargs):
        run_calls.append((app, kwargs))

    monkeypatch.setattr("uvicorn.run", fake_run)

    rc = _cmd_serve(cfg_path, host="127.0.0.1", port=9999)

    assert rc == 0
    assert run_calls
    assert run_calls[0][1]["host"] == "127.0.0.1"
    assert run_calls[0][1]["port"] == 9999
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        table = conn.execute(
            """
            select name from sqlite_master
            where type = 'table' and name = 'item_external_links'
            """
        ).fetchone()
    assert table == ("item_external_links",)


def test_seed_demo_runs_migrations_for_empty_database(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")

    rc = asyncio.run(_cmd_seed_demo(cfg_path, "example", force_reset=False))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        item_count = conn.execute(
            "select count(*) from items where project_key = 'example'"
        ).fetchone()[0]
        external_link_table = conn.execute(
            """
            select name from sqlite_master
            where type = 'table' and name = 'item_external_links'
            """
        ).fetchone()
    assert item_count == 8
    assert external_link_table == ("item_external_links",)


def test_create_item_cli_creates_local_item_with_metadata(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    project_path = tmp_path / "projects" / "example.toml"
    project_path.write_text(
        project_path.read_text(encoding="utf-8") + "\n".join([
            "",
            "[custom_fields.priority]",
            'label = "Priority"',
            'type = "select"',
            'options = ["low", "high"]',
            "",
        ]),
        encoding="utf-8",
    )

    rc = asyncio.run(_cmd_create_item(
        cfg_path,
        "example",
        kind="bug",
        title="Fix CLI create",
        body="Created from the terminal.",
        body_file=None,
        tags=["cli", "triage"],
        applies_to=["main"],
        custom_field_options=["priority=high"],
        external_link_options=["Spec | https://example.com/spec"],
        dry_run=False,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["local_id"].startswith("BUG-")
    assert payload["kind"] == "bug"
    assert payload["title"] == "Fix CLI create"
    assert payload["tags"] == ["cli", "triage"]
    assert payload["applies_to"] == ["main"]
    assert payload["custom_fields"] == {"priority": "high"}
    assert payload["external_links"][0]["label"] == "Spec"
    assert payload["external_links"][0]["url"] == "https://example.com/spec"


def test_create_item_cli_dry_run_reads_body_file_without_writing(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    body_path = tmp_path / "body.md"
    body_path.write_text("Body from file.", encoding="utf-8")

    rc = asyncio.run(_cmd_create_item(
        cfg_path,
        "example",
        kind=None,
        title="Plan terminal workflow",
        body=None,
        body_file=body_path,
        tags=[],
        applies_to=None,
        custom_field_options=[],
        external_link_options=[],
        dry_run=True,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "feature"
    assert payload["body"] == "Body from file."
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        item_count = conn.execute(
            "select count(*) from items where project_key = 'example'"
        ).fetchone()[0]
    assert item_count == 8


def test_update_item_cli_updates_local_item_with_metadata(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    project_path = tmp_path / "projects" / "example.toml"
    project_path.write_text(
        project_path.read_text(encoding="utf-8") + "\n".join([
            "",
            "[custom_fields.priority]",
            'label = "Priority"',
            'type = "select"',
            'options = ["low", "high"]',
            "",
        ]),
        encoding="utf-8",
    )

    rc = asyncio.run(_cmd_update_item(
        cfg_path,
        "example",
        "FEAT-0001",
        title="Updated from CLI",
        status="in_progress",
        body="Replacement body.",
        body_file=None,
        append_body=None,
        append_body_file=None,
        tags=["cli", "updated"],
        applies_to=["main"],
        custom_field_options=["priority=high"],
        external_link_options=["https://example.com/update"],
        clear_external_links=False,
        dry_run=False,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["local_id"] == "FEAT-0001"
    assert payload["title"] == "Updated from CLI"
    assert payload["status"] == "in_progress"
    assert payload["tags"] == ["cli", "updated"]
    assert payload["custom_fields"] == {"priority": "high"}
    assert payload["external_links"][0]["url"] == "https://example.com/update"
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        body = conn.execute(
            """
            select body from items
            where project_key = 'example' and local_id = 'FEAT-0001'
            """
        ).fetchone()[0]
    assert body == "Replacement body."


def test_update_item_cli_dry_run_reads_append_body_file_without_writing(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    body_path = tmp_path / "append.md"
    body_path.write_text("Append from file.", encoding="utf-8")

    rc = asyncio.run(_cmd_update_item(
        cfg_path,
        "example",
        "FEAT-0001",
        title=None,
        status=None,
        body=None,
        body_file=None,
        append_body=None,
        append_body_file=body_path,
        tags=None,
        applies_to=None,
        custom_field_options=[],
        external_link_options=None,
        clear_external_links=False,
        dry_run=True,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"append_body": "Append from file."}
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        title = conn.execute(
            """
            select title from items
            where project_key = 'example' and local_id = 'FEAT-0001'
            """
        ).fetchone()[0]
    assert title != "Updated from CLI"


def test_bulk_update_items_cli_updates_multiple_items(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    project_path = tmp_path / "projects" / "example.toml"
    project_path.write_text(
        project_path.read_text(encoding="utf-8") + "\n".join([
            "",
            "[custom_fields.priority]",
            'label = "Priority"',
            'type = "select"',
            'options = ["low", "high"]',
            "",
        ]),
        encoding="utf-8",
    )
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        local_ids = [
            row[0]
            for row in conn.execute(
                """
                select local_id from items
                where project_key = 'example' and kind = 'feature'
                order by local_id
                limit 2
                """
            ).fetchall()
        ]

    rc = asyncio.run(_cmd_bulk_update_items(
        cfg_path,
        "example",
        local_ids,
        action="update",
        kind=None,
        status="in_progress",
        tags=["triaged"],
        tag_mode="replace",
        applies_to=["main"],
        custom_field_options=["priority=high"],
        reason="cli test",
        dry_run=False,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["requested_count"] == 2
    assert payload["updated_count"] == 2
    assert [item["local_id"] for item in payload["items"]] == local_ids
    assert [item["status"] for item in payload["items"]] == [
        "in_progress",
        "in_progress",
    ]
    assert [item["tags"] for item in payload["items"]] == [
        ["triaged"],
        ["triaged"],
    ]
    assert [item["custom_fields"] for item in payload["items"]] == [
        {"priority": "high"},
        {"priority": "high"},
    ]


def test_bulk_update_items_cli_dry_run_without_writing(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_bulk_update_items(
        cfg_path,
        "example",
        ["FEAT-0001"],
        action="delete",
        kind=None,
        status=None,
        tags=None,
        tag_mode="add",
        applies_to=None,
        custom_field_options=[],
        reason="cleanup",
        dry_run=True,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "delete"
    assert payload["local_ids"] == ["FEAT-0001"]
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        deleted_at = conn.execute(
            """
            select deleted_at from items
            where project_key = 'example' and local_id = 'FEAT-0001'
            """
        ).fetchone()[0]
    assert deleted_at is None


def test_list_items_cli_prints_filtered_table(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_list_items(
        cfg_path,
        "example",
        kinds=["feature"],
        statuses=[],
        tags=[],
        applies_to=[],
        relation_types=[],
        custom_field_options=[],
        include_deleted=False,
        only_deleted=False,
        limit=5,
        output_format="table",
    ))

    assert rc == 0
    out = capsys.readouterr().out
    assert "ID" in out
    assert "Kind" in out
    assert "feature" in out
    assert "bug" not in out


def test_list_items_cli_supports_json_and_custom_field_filters(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    project_path = tmp_path / "projects" / "example.toml"
    project_path.write_text(
        project_path.read_text(encoding="utf-8") + "\n".join([
            "",
            "[custom_fields.priority]",
            'label = "Priority"',
            'type = "select"',
            'options = ["low", "high"]',
            "",
        ]),
        encoding="utf-8",
    )
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        conn.execute(
            """
            update items
            set custom_fields_json = '{"priority":"high"}'
            where pk = (select pk from items order by pk limit 1)
            """
        )

    rc = asyncio.run(_cmd_list_items(
        cfg_path,
        "example",
        kinds=[],
        statuses=[],
        tags=[],
        applies_to=[],
        relation_types=[],
        custom_field_options=["priority=high"],
        include_deleted=False,
        only_deleted=False,
        limit=10,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["custom_fields"] == {"priority": "high"}


def test_get_item_cli_prints_item_detail(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_get_item(
        cfg_path,
        "example",
        "FEAT-0001",
        include_deleted=False,
        output_format="text",
    ))

    assert rc == 0
    out = capsys.readouterr().out
    assert "FEAT-0001" in out
    assert "feature" in out


def test_get_item_cli_supports_json(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_get_item(
        cfg_path,
        "example",
        "FEAT-0001",
        include_deleted=False,
        output_format="json",
    ))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["local_id"] == "FEAT-0001"
    assert payload["kind"] == "feature"


def test_export_audit_bundle_cli_writes_zip(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    out_path = tmp_path / "audit.zip"
    rc = asyncio.run(_cmd_export_audit_bundle(cfg_path, "example", out_path))

    assert rc == 0
    assert out_path.exists()
    with zipfile.ZipFile(out_path) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["project_key"] == "example"
        assert manifest["counts"]["items"] == 8
        assert "items.json" in bundle.namelist()


def test_import_github_url_dry_run_prints_create_payload(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_import_github_url(
        cfg_path,
        "example",
        "https://github.com/example/repo/issues/42",
        kind="bug",
        title=None,
        body=None,
        tags=[],
        applies_to=None,
        link_label=None,
        dry_run=True,
    ))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "bug"' in out
    assert '"title": "Review GitHub issue #42 from example/repo"' in out
    assert '"link_type": "github_issue"' in out


def test_import_github_url_creates_linked_item(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_import_github_url(
        cfg_path,
        "example",
        "https://github.com/example/repo/pull/7",
        kind="feature",
        title="Track upstream PR",
        body=None,
        tags=["upstream"],
        applies_to=["main"],
        link_label=None,
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select items.title, item_external_links.link_type, item_external_links.url
            from items
            join item_external_links on item_external_links.item_pk = items.pk
            where items.title = 'Track upstream PR'
            """
        ).fetchone()
    assert row == (
        "Track upstream PR",
        "github_pr",
        "https://github.com/example/repo/pull/7",
    )

    rc = _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        item_count = conn.execute(
            "select count(*) from items where project_key = 'example'"
        ).fetchone()[0]
    assert item_count == 9


def test_import_github_url_runs_migrations_for_empty_database(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")

    rc = asyncio.run(_cmd_import_github_url(
        cfg_path,
        "example",
        "https://github.com/example/repo/issues/42",
        kind="bug",
        title=None,
        body=None,
        tags=[],
        applies_to=None,
        link_label=None,
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select items.title, item_external_links.link_type
            from items
            join item_external_links on item_external_links.item_pk = items.pk
            where items.local_id = 'BUG-0001'
            """
        ).fetchone()
    assert row == (
        "Review GitHub issue #42 from example/repo",
        "github_issue",
    )


def test_import_github_issues_dry_run_uses_fetcher(tmp_path, monkeypatch, capsys):
    from issuedeck.features.migrate.github_issues import (
        GitHubIssueImportReport,
        GitHubIssueRow,
    )

    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")

    async def fake_fetch(repo, **kwargs):
        assert repo.owner == "example"
        assert repo.repo == "repo"
        assert kwargs["state"] == "all"
        assert kwargs["labels"] == ["bug"]
        return (
            [
                GitHubIssueRow(
                    number=42,
                    title="Fix auth",
                    body="Body",
                    state="open",
                    labels=["bug"],
                    html_url="https://github.com/example/repo/issues/42",
                    api_url="https://api.github.com/repos/example/repo/issues/42",
                    author="octo",
                    created_at="2026-01-01T00:00:00Z",
                    updated_at="2026-01-02T00:00:00Z",
                    comments=0,
                    is_pull_request=False,
                )
            ],
            GitHubIssueImportReport(issues_fetched=1),
        )

    monkeypatch.setattr(
        "issuedeck.features.migrate.github_issues.fetch_github_issue_rows",
        fake_fetch,
    )

    rc = asyncio.run(_cmd_import_github_issues(
        cfg_path,
        "example",
        "example/repo",
        kind="feature",
        default_status=None,
        tags=["imported"],
        applies_to=None,
        status_maps=[],
        state="all",
        labels=["bug"],
        since=None,
        limit=10,
        include_pulls=False,
        github_token=None,
        dry_run=True,
    ))

    assert rc == 0
    err = capsys.readouterr().err
    assert "[dry-run] repo=example/repo" in err
    assert "fetched=1" in err
    assert "planned=1" in err


def test_import_markdown_list_creates_items_from_tasks(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")
    source = tmp_path / "TODO.md"
    source.write_text(
        "\n".join([
            "- [ ] Import markdown task",
            "- [x] Skip checked by default",
        ]),
        encoding="utf-8",
    )

    rc = asyncio.run(_cmd_import_markdown_list(
        cfg_path,
        "example",
        source,
        kind="feature",
        tags=["todo"],
        applies_to=None,
        include_checked=False,
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select local_id, title, status
            from items
            where project_key = 'example'
            """
        ).fetchone()
        tags = conn.execute(
            """
            select tag from item_tags
            join items on items.pk = item_tags.item_pk
            order by tag
            """
        ).fetchall()
    assert row == ("FEAT-0001", "Import markdown task", "proposed")
    assert tags == [("markdown",), ("todo",)]


def test_import_csv_creates_items_from_tracker_export(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")
    source = tmp_path / "issues.csv"
    source.write_text(
        "\n".join([
            "Issue,Type,State,Labels,Branches,URL,Description,ID",
            (
                "Import CSV export,Bug,Verified,\"migration,urgent\",Main,"
                "https://github.com/example/repo/issues/42,"
                "Keep importer notes,GH-42"
            ),
        ]),
        encoding="utf-8",
    )

    rc = asyncio.run(_cmd_import_csv(
        cfg_path,
        "example",
        source,
        kind="feature",
        default_status=None,
        tags=["imported"],
        applies_to=None,
        presets=["github"],
        field_aliases=["title=Issue"],
        status_maps=["Verified=done"],
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select items.local_id, items.kind, items.status, items.title,
                   item_external_links.link_type
            from items
            join item_external_links on item_external_links.item_pk = items.pk
            where items.title = 'Import CSV export'
            """
        ).fetchone()
        tags = conn.execute(
            """
            select tag from item_tags
            join items on items.pk = item_tags.item_pk
            where items.title = 'Import CSV export'
            order by tag
            """
        ).fetchall()
        applies_to = conn.execute(
            """
            select branch_key from item_applies_to
            join items on items.pk = item_applies_to.item_pk
            where items.title = 'Import CSV export'
            """
        ).fetchall()
    assert row == ("BUG-0001", "bug", "done", "Import CSV export", "github_issue")
    assert tags == [("csv",), ("imported",), ("migration",), ("urgent",)]
    assert applies_to == [("main",)]


def test_import_json_creates_items_from_tracker_export(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")
    source = tmp_path / "issues.json"
    source.write_text(
        """
        {
          "issues": [
            {
              "title": "Import JSON export",
              "type": "Bug",
              "state": "Verified",
              "labels": ["migration", "urgent"],
              "branches": ["main"],
              "html_url": "https://github.com/example/repo/issues/42",
              "body": "Keep importer notes",
              "number": 42
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    rc = asyncio.run(_cmd_import_json(
        cfg_path,
        "example",
        source,
        kind="feature",
        default_status=None,
        tags=["imported"],
        applies_to=None,
        presets=["github"],
        field_aliases=[],
        status_maps=["Verified=done"],
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select items.local_id, items.kind, items.status, items.title,
                   item_external_links.link_type
            from items
            join item_external_links on item_external_links.item_pk = items.pk
            where items.title = 'Import JSON export'
            """
        ).fetchone()
        tags = conn.execute(
            """
            select tag from item_tags
            join items on items.pk = item_tags.item_pk
            where items.title = 'Import JSON export'
            order by tag
            """
        ).fetchall()
    assert row == ("BUG-0001", "bug", "done", "Import JSON export", "github_issue")
    assert tags == [("imported",), ("json",), ("migration",), ("urgent",)]


def test_cli_registry_rejects_project_key_filename_mismatch(tmp_path):
    projects_dir = tmp_path / "projects"
    data_dir = tmp_path / "data"
    projects_dir.mkdir()
    data_dir.mkdir()
    (tmp_path / "server.toml").write_text(
        "\n".join([
            'api_token = "token"',
            f'projects_dir = "{projects_dir.as_posix()}"',
            f'data_dir = "{data_dir.as_posix()}"',
        ]),
        encoding="utf-8",
    )
    (projects_dir / "demo.toml").write_text(
        "\n".join([
            'key = "other"',
            'name = "Other"',
            "[kinds.feature]",
            'label = "Feature"',
            'prefix = "FEAT"',
            "[statuses.proposed]",
            'label = "Proposed"',
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="filename stem"):
        _build_registry(tmp_path / "server.toml")
