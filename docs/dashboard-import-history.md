# Dashboard Import History

[简体中文](dashboard-import-history.zh-CN.md)

Dashboard import history records successful GitHub, CSV, JSON, and Markdown
imports that wrote at least one item.

Open a project and choose **Import History** from the sidebar. Each entry shows
the source, batch tag, created time, planned and written counts, skipped count,
status mappings, external link count, and the current active/deleted item
counts for that batch.

Every recorded import includes a **Triage batch** link. It opens the list view
filtered by that import's batch tag, so you can return to the same batch later
without remembering the tag name.

Use **Soft-delete batch** when an import was wrong or duplicated. IssueDeck
finds the active items with that batch tag, soft-deletes them in bulk, and
leaves the import history record visible for audit context.

Use **Restore batch** to bring back deleted items from that same batch. Restore
only targets items that are already soft-deleted, so it can safely recover a
mistaken batch delete without duplicating active work.

The delete and restore actions are disabled when there are no matching active or
deleted items, making the history page safe to scan before acting.

Preview-only imports are not recorded because they do not write items. Formal
imports that write zero items are also omitted from the history.
