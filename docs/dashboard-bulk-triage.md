# Dashboard Bulk Triage

[简体中文](dashboard-bulk-triage.zh-CN.md)

Bulk triage helps clean up imported or newly captured work without opening each
item one by one.

Dashboard GitHub imports add a per-run `github-import-YYYYMMDD-HHMMSS-xxxx`
batch tag and show a result link to the list filtered by that tag. Use that
entry point to review only the items written by the latest import.

Open a project, go to **List**, select one or more visible items, then use the
bulk triage bar above the list.

## Supported Actions

- Update status, excluding statuses that require a ship record.
- Update kind while keeping each item's existing local ID.
- Add, remove, or replace tags.
- Replace target branches.
- Soft delete selected items.
- Restore selected deleted items when the current view includes deleted items.

After applying a bulk action, IssueDeck redirects back to the same filtered list
URL and shows the result count.

## REST API

```bash
curl -X POST http://127.0.0.1:8765/api/v1/projects/example/items/bulk \
  -H "Authorization: Bearer $ISSUEDECK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "local_ids": ["FEAT-0001", "BUG-0002"],
    "status": "in_progress",
    "tags": ["triaged"],
    "tag_mode": "add",
    "applies_to": ["main"]
  }'
```

Use `"action": "delete"` or `"action": "restore"` for lifecycle operations.
The response includes requested and updated counts plus the updated item
summaries.
