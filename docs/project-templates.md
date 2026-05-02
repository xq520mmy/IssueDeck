# Project Templates

IssueDeck can create new project configs from starter templates in the
dashboard. Open `/dashboard/projects-new`, enter the project key and name, then
choose a template before submitting.

Templates write a normal `projects/<key>.toml` file. After creation, you can
edit that TOML to rename kinds, add statuses, change prefixes, or add release
branches.

## Local Template Packs

To add templates without changing IssueDeck source code, place TOML files in
`project_templates_dir` from `server.toml`:

```toml
project_templates_dir = "./project-templates"
```

Each `*.toml` file describes one starter template:

```toml
key = "support"
name = "Support queue"
description = "Customer support triage with escalation states."
ship_exempt_kinds = ["question"]

[[kinds]]
key = "question"
label = "Question"
prefix = "QST"

[[kinds]]
key = "incident"
label = "Incident"
prefix = "INC"

[[statuses]]
key = "new"
label = "New"

[[statuses]]
key = "investigating"
label = "Investigating"

[[statuses]]
key = "resolved"
label = "Resolved"
terminal = true

[[branches]]
key = "support"
label = "Support"
```

Custom template keys cannot duplicate built-in keys. If a status uses
`requires_ship = true`, the template must define at least one branch. Local
template packs often encode team-specific workflow names, so the default
`.gitignore` keeps `project-templates/*.toml` private unless you explicitly
publish an example.

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
