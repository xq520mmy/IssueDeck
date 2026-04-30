# Dashboard Accessibility Smoke Checklist

[简体中文](accessibility-checklist.zh-CN.md)

Use this checklist for dashboard UI changes. It is intentionally lightweight:
the goal is to catch obvious regressions before a pull request lands.

## Keyboard

- `Tab` and `Shift+Tab` move through visible controls in a predictable order.
- Focus never gets trapped in sidebars, menus, dialogs, or saved-filter controls.
- Buttons, links, checkboxes, selects, and form submits work with keyboard input.
- `Escape` closes transient UI when that pattern already exists in the view.
- The current item or control is still visible after keyboard navigation.

## Focus and State

- Focus styles are visible against the surrounding background.
- Disabled controls look disabled and are not reachable by keyboard.
- Loading, empty, error, and success states do not shift the layout unexpectedly.
- Dynamic lists, kanban columns, and detail panels keep stable dimensions while
  counts or labels change.

## Labels and Forms

- Every input has a visible label or a programmatic label.
- Required fields and validation errors are clear without relying only on color.
- Error messages appear near the field or action that caused them.
- Icon-only controls have an accessible name and, when useful, a tooltip.

## Color and Contrast

- Body text, labels, badges, and buttons are readable in normal and hover states.
- Status colors have text labels or icons; color alone is not the only signal.
- Selected, active, blocked, deleted, and done states remain distinguishable in
  grayscale or reduced contrast.

## Language and Responsive Layout

- English and Simplified Chinese labels fit inside buttons, tabs, filters, and
  mobile cards.
- Switching languages does not leave stale text in navigation, forms, empty
  states, or action buttons.
- Test at desktop width, tablet width, and a narrow mobile viewport.
- Text does not overlap adjacent cards, tables, toolbars, or sticky navigation.

## Pull Request Evidence

For dashboard PRs, include the manual checks you ran. A short note is enough:

```text
Accessibility smoke:
- Keyboard: search, create item, saved filter menu, item detail actions
- Viewports: 1440px, 768px, 390px
- Languages: English and Simplified Chinese
```
