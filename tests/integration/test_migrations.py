from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(Path.cwd() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path):
    db = tmp_path / "t.db"
    command.upgrade(_alembic_config(db), "head")

    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    expected = {
        "items", "item_tags", "item_applies_to",
        "ship_records", "ship_commits", "item_relationships", "item_events",
        "items_fts", "alembic_version",
    }
    assert expected.issubset(names)


def test_fts5_triggers_sync_on_insert(tmp_path):
    db = tmp_path / "t.db"
    command.upgrade(_alembic_config(db), "head")
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO items (project_key, local_id, kind, status, title, "
            "body, created_at, updated_at) VALUES "
            "('p', 'FEAT-0001', 'feature', 'proposed', 'hello world',"
            " 'some body text', 't', 't')"
        ))
        hits = conn.execute(text(
            "SELECT rowid FROM items_fts WHERE items_fts MATCH 'hello'"
        )).scalars().all()
    assert len(hits) == 1


def test_downgrade_drops_tables(tmp_path):
    db = tmp_path / "t.db"
    cfg = _alembic_config(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert "items" not in names
