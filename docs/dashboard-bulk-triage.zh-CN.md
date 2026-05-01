# Dashboard 批量分诊

[English](dashboard-bulk-triage.md)

批量分诊适合整理刚导入或刚捕获的一批事项，不需要逐个打开详情页修改。

Dashboard GitHub 和文件导入都会给每次写入自动添加批次标签，例如
`github-import-YYYYMMDD-HHMMSS-xxxx` 或 `csv-import-...`，并在结果页提供按这个
标签筛选的列表入口。可以从这里只审阅最新导入的事项。

打开项目后进入 **列表**，勾选一个或多个当前可见事项，然后使用列表上方的批量分诊栏。

## 支持操作

- 批量更新状态，但会排除需要 ship record 的状态。
- 批量更新类型，同时保留每个事项原有 local ID。
- 批量添加、移除或替换标签。
- 批量替换目标分支。
- 批量软删除选中的事项。
- 当前视图包含已删除事项时，可以批量恢复。

执行后，IssueDeck 会回到同一个筛选后的列表 URL，并显示处理数量。

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

生命周期操作可传 `"action": "delete"` 或 `"action": "restore"`。响应会返回请求数量、
更新数量和更新后的 item summary。
