import gzip
import shutil
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(Path.cwd() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_restore_smoke_accepts_gzipped_backup(tmp_path):
    source = tmp_path / "tracker.db"
    command.upgrade(_alembic_config(source), "head")

    engine = create_engine(f"sqlite:///{source}")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO items (project_key, local_id, kind, status, title, "
            "body, created_at, updated_at) VALUES "
            "('demo', 'FEAT-0001', 'feature', 'proposed', 'hello', '', 't', 't')"
        ))

    backup = tmp_path / "tracker-test.db.gz"
    with source.open("rb") as raw, gzip.open(backup, "wb") as zipped:
        shutil.copyfileobj(raw, zipped)

    restored = tmp_path / "restored.db"
    result = subprocess.run(
        [sys.executable, "scripts/restore_smoke.py", str(backup), "--out", str(restored)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert restored.exists()
    assert "[ok] integrity_check=ok" in result.stdout
    assert "[ok] items=1 projects=1" in result.stdout
