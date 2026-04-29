"""Markdown-bundle export — one .md file per item under <out_dir>/items/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.models import Item, ShipRecord


@dataclass
class ExportReport:
    items_written: int


async def export_md_bundle(
    *, session: AsyncSession, registry: ConfigRegistry,
    project_key: str, out_dir: Path,
) -> ExportReport:
    registry.project(project_key)  # raises ProjectNotFound if missing

    items = (await session.execute(
        select(Item)
        .where(Item.project_key == project_key, Item.deleted_at.is_(None))
        .order_by(Item.local_id)
        .options(
            selectinload(Item.tags),
            selectinload(Item.applies_to),
            selectinload(Item.ship_records).selectinload(ShipRecord.commits),
        )
    )).scalars().all()

    items_dir = out_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        (items_dir / f"{item.local_id}.md").write_text(
            _render_item_md(item), encoding="utf-8",
        )

    return ExportReport(items_written=len(items))


def _render_item_md(item: Item) -> str:
    lines: list[str] = ["---"]
    lines.append(f"id: {item.local_id}")
    lines.append(f"kind: {item.kind}")
    lines.append(f"status: {item.status}")
    lines.append(f"title: {_yaml_quote(item.title)}")
    if item.tags:
        lines.append("tags:")
        for t in item.tags:
            lines.append(f"  - {t.tag}")
    if item.applies_to:
        applies = ", ".join(a.branch_key for a in item.applies_to)
        lines.append(f"applies_to: [{applies}]")
    for sr in item.ship_records:
        lines.append(f"shipped_in_{sr.branch_key}: {sr.version}")
        if sr.commits:
            lines.append(f"commits_{sr.branch_key}:")
            for c in sr.commits:
                lines.append(f"  - {c.sha}")
    lines.append(f"created_at: {item.created_at}")
    lines.append(f"updated_at: {item.updated_at}")
    lines.append("---")
    lines.append("")
    lines.append(item.body or "")
    return "\n".join(lines) + "\n"


def _yaml_quote(s: str) -> str:
    if any(c in s for c in ":#\"'\n"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s
