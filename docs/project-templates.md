# Project Templates

IssueDeck can create new project configs from starter templates in the
dashboard. Open `/dashboard/projects-new`, enter the project key and name, then
choose a template before submitting.

Templates write a normal `projects/<key>.toml` file. After creation, you can
edit that TOML to rename kinds, add statuses, change prefixes, or add release
branches.

## Built-In Templates

| Template | Best for | Includes |
| --- | --- | --- |
| Basic issue deck | Demos and lightweight personal backlogs | Feature, Bug, Improvement; Proposed, In Progress, Done, Won't Fix; Main branch |
| Agent workflow | Human plus AI coding-agent triage | Feature, Bug, Improvement, Task; Proposed, In Progress, Blocked, Ready to Ship, Done, Won't Fix; Main branch |
| Software team | Broader product delivery boards | Epic, Feature, Bug, Chore; Backlog, Ready, In Progress, Review, Done, Won't Fix; Main and Release branches |

## Notes

- Project keys must stay lowercase and URL-safe, for example `acme-web`.
- The selected template only affects the initial TOML. Existing projects are
  never rewritten by changing templates later.
- Statuses with `requires_ship = true` still follow normal IssueDeck ship
  rules.
