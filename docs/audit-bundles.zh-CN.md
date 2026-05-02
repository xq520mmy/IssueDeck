# 审计导出包

审计导出包是一个 ZIP 快照，适合团队定期归档项目、交接上下文，或在迁移前保存
轻量检查点。

```bash
uv run issuedeck export-audit-bundle \
  --project-key example \
  --out snapshots/
```

如果 `--out` 是目录，IssueDeck 会写入
`snapshots/example-audit-bundle.zip`。如果它以 `.zip` 结尾，IssueDeck 会写入
这个明确指定的文件。

## 包内容

- `manifest.json`：导出包格式、项目键、生成时间、计数和文件列表。
- `project.json`：解析后的项目配置。
- `project.toml`：磁盘上的原始项目配置，存在时会一起打包。
- `items.json`：活跃和已删除事项，包含标签、目标分支、外部链接、发布记录和生命周期事件。
- `relationships.json`：项目内全部关系行，包括双向反向关系。
- `work_sessions.json`：agent 工作会话和进展更新。
- `import_batches.json`：Dashboard 和 CLI 导入历史元数据。

导出包是只读快照，不会修改项目数据。
