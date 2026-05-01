# 维护者工作流规范

[English](maintainer-workflow.md)

这份文档用于统一 IssueDeck 维护者和后续 AI coding 窗口的工作方式：从需求确认、
实现、验证、提交、推送到 CI 检查，都按同一套标准执行。

## 目标

- 每个改动都能从需求追溯到 commit。
- 保护真实项目数据、本地运行数据和密钥。
- 让后续窗口无需重新问规则，也能安全接手。
- 保持开源仓库专业：双语文档、测试通过、历史干净、页面不残留旧状态。

## 需求进入标准

开始实现前，先写清楚或合理推断最小可交付需求：

- 问题：解决什么用户痛点或产品缺口？
- 用户：面向 Dashboard 用户、CLI 用户、MCP 客户端，还是维护者？
- 结果：完成后用户能做什么？
- 验收标准：页面行为、API/CLI 形态、边界情况和错误提示。
- 非目标：这次明确不做什么？
- 风险：是否涉及迁移、密钥、真实数据、公开文档、部署或 UI？

较大的功能应先创建或更新 GitHub issue。issue 里至少包含背景、范围、验收标准、
测试计划，以及必要的截图或示例。

## 计划标准

动手前用这份短计划对齐：

1. 找到受影响的 feature slice 和现有模式。
2. 判断是否需要测试、文档、i18n、迁移或 CSS 生成。
3. 明确本地复现或预览路径。
4. 明确必须通过的验证命令。
5. 控制范围，让 reviewer 能快速理解。

## 实现标准

- 沿用现有结构：`routes -> service -> repo -> models -> schemas`。
- 优先使用现有 helper 和 domain service，不轻易新增抽象。
- 数据库结构变化必须加 Alembic migration。
- 不提交运行时数据、生成归档、本地数据库或私有配置。
- 文档、fixture、截图和示例一律使用假数据。
- Dashboard 文案变化要同时更新
  `src/issuedeck/features/dashboard/i18n.py` 的 `en` 和 `zh-CN`。
- Dashboard template、helper class map 或 Tailwind 配置变化后，运行
  `npm run build:css`，并提交生成的 dashboard CSS。
- 用户可见变化要更新 `CHANGELOG.md`。
- 用户文档原则上中英文都补齐。

## UI 与 i18n 标准

- 改 Dashboard UI 前先读 `DESIGN.md`。
- Dashboard 风格保持密集、结构化、贴近代码、可信赖。
- 页面可见字符串必须走 i18n。
- 检查 HTML 中不能出现 `nav.import_history`、`nav.import_files`、
  `bulk.action` 这类原始翻译 key。
- 重要 Dashboard 改动需要本地浏览器或 HTTP 预览验证。
- 服务端渲染的 Dashboard HTML 使用 `Cache-Control: no-store`，避免本地预览看到旧翻译页面。

## 测试标准

行为变更先跑相关测试，再在提交前跑全量测试。

通用命令：

```bash
uv run ruff check .
uv run pytest
git diff --check
```

当前 Windows 维护机常用命令：

```powershell
C:\Python313\python.exe -m uv run ruff check .
C:\Python313\python.exe -m uv run pytest
git diff --check
```

Dashboard CSS 可能变化时：

```bash
npm run build:css
```

打包或发版前：

```bash
uv build
```

## 本地预览标准

本地预览只使用假 token，不打印真实密钥。

```powershell
$env:ISSUEDECK_API_TOKEN = "set-via-ISSUEDECK_API_TOKEN-env"
C:\Python313\python.exe -m uv run issuedeck demo --config server.toml --project-key example --host 127.0.0.1 --port 8775
```

如果浏览器出现旧 UI 或原始 i18n key：

1. 检查 `8775-8778` 端口是否残留旧 IssueDeck 进程。
2. 停掉旧预览进程。
3. 只在 `8775` 启动一个当前代码服务。
4. 重新打开受影响页面，并确认 HTML 中不再包含原始翻译 key。

## Git 标准

提交前先看状态和 diff：

```bash
git status --short
git diff --stat
git diff --check
```

只 stage 明确相关文件：

```bash
git add path/to/file path/to/other-file
```

commit message 使用 Conventional Commits：

- `feat:` 用户可见功能。
- `fix:` bug 修复。
- `docs:` 纯文档。
- `test:` 纯测试。
- `refactor:` 不改变行为的代码整理。
- `chore:` 工具、维护、生成元数据或杂项。

示例：

```text
feat: add import batch soft delete
fix: prevent stale dashboard translations
docs: add maintainer workflow
```

本维护机推送命令：

```powershell
$env:GIT_CONFIG_GLOBAL = "NUL"
git push origin main
```

## CI 验证标准

推送后必须确认当前 SHA 的 GitHub Actions。至少关注：

- `ci`
- `docker`

最终交接信息要包含：

- commit SHA 和 message。
- 本地跑过的检查及结果。
- 远端 CI/Docker 链接。
- 如果涉及 UI，给出本地预览 URL。
- 未解决风险或后续项。

## 发版标准

日常开发：

- 用户可见变化写入 `CHANGELOG.md` 的 `[Unreleased]`。
- 不准备真实发版时，不随意 bump 版本号。
- 测试、Docker、文档和 changelog 没准备好前，不打 tag。

正式发版：

1. 检查 `RELEASE_CHECKLIST.md`。
2. 确认 `pyproject.toml` 和 `package.json` 版本号。
3. 确认 `CHANGELOG.md` 已整理成带日期的发布段落。
4. 跑全量测试和 build。
5. 推送、确认 CI、创建 tag/release，并验证发布产物。

## 安全与隐私

- 不提交 `.env`、真实 token、私有项目配置、真实 tracker 数据、数据库文件、归档包或部署产物。
- 公开发布前搜索私有名称。
- 示例统一使用假项目名和假 issue 数据。
- token 一律走环境变量。
- 日志和最终报告中隐藏凭据。

## 完成定义

满足以下条件才算完成：

- 需求已经实现。
- 行为变化有测试覆盖，或明确说明无法覆盖的风险。
- 必要的文档、i18n、CHANGELOG、CSS、migration 和示例已更新。
- `ruff`、`pytest`、`git diff --check` 通过。
- UI 改动已本地预览。
- 如果用户要求自主完成或公开发布，commit 已推送且远端 CI 通过。
