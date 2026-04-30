# Dashboard 可访问性 Smoke Checklist

[English](accessibility-checklist.md)

Dashboard UI 变更可以用这份轻量检查清单。目标不是替代完整审计，而是在 PR 合入前抓住
明显回归。

## 键盘操作

- `Tab` 和 `Shift+Tab` 会按可预测顺序经过可见控件。
- 焦点不会卡在 sidebar、menu、dialog 或 saved-filter 控件里。
- 按钮、链接、checkbox、select 和表单提交都可以用键盘操作。
- 当前视图已经有临时 UI 时，`Escape` 可以按既有模式关闭它。
- 键盘导航后，当前事项或控件仍在可见区域内。

## 焦点和状态

- Focus 样式在周围背景上清晰可见。
- Disabled 控件看起来不可用，并且不能被键盘聚焦。
- Loading、empty、error、success 状态不会让布局异常跳动。
- 动态列表、kanban 列和详情面板在计数或标签变化时保持稳定尺寸。

## 标签和表单

- 每个 input 都有可见 label 或 programmatic label。
- 必填字段和校验错误不能只依赖颜色表达。
- 错误信息出现在相关字段或操作附近。
- 只有 icon 的控件需要 accessible name，必要时加 tooltip。

## 颜色和对比度

- 正常和 hover 状态下，正文、标签、badge、按钮都要可读。
- 状态颜色需要配合文字或 icon；不能只用颜色传达含义。
- Selected、active、blocked、deleted、done 状态在灰度或低对比环境下仍能区分。

## 语言和响应式布局

- 英文和简体中文标签都能放进按钮、tab、filter、移动端卡片。
- 切换语言后，导航、表单、empty state、action button 不应残留旧语言文本。
- 至少测试桌面、平板和窄移动端宽度。
- 文本不能和相邻卡片、表格、toolbar 或 sticky navigation 重叠。

## PR 说明

Dashboard PR 里请写清楚做过哪些手动检查。简短说明即可：

```text
Accessibility smoke:
- Keyboard: search, create item, saved filter menu, item detail actions
- Viewports: 1440px, 768px, 390px
- Languages: English and Simplified Chinese
```
