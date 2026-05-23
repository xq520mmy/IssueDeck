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

[custom_fields.priority]
label = "Priority"
type = "select"
options = ["low", "high"]

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
template packs can also include project `custom_fields`. They often encode
team-specific workflow names, so the default `.gitignore` keeps
`project-templates/*.toml` private unless you explicitly publish an example.

Validate a template pack before sharing it:

```bash
issuedeck validate-project-templates ./project-templates
issuedeck validate-project-templates ./project-templates --format json
```

The command checks every `*.toml` file, reports invalid templates without
stopping at the first failure, and exits with code `2` when any template needs
fixing. If you omit the directory argument, IssueDeck reads
`project_templates_dir` from `server.toml`.

## Example Template Packs

IssueDeck ships installable example packs for common workflows:

| Example | Best for | Highlights |
| --- | --- | --- |
| `support` | Customer support queues and incident follow-up | Questions, incidents, requests, SLA risk, customer, source URL |
| `content` | Editorial and content calendars | Ideas, drafts, assets, publishing channels, publish window |
| `research` | Discovery and validation work | Questions, experiments, findings, decisions, confidence, effort |

List the available examples:

```bash
issuedeck list-project-template-examples
issuedeck list-project-template-examples --format json
```

Install one into your local template pack directory:

```bash
issuedeck install-project-template-example support --config server.toml
issuedeck install-project-template-example research \
  --templates-dir ./project-templates
```

Use `--dry-run` to preview the TOML before writing it, and `--force` to replace
an example file that already exists. After installing an example, it appears in
`issuedeck list-project-templates` and in the dashboard project creation form.
The dashboard project creation page can also install these examples directly.

## Export A Project As A Template

After you tune a project workflow in `projects/<key>.toml`, export it as a
reusable template pack:

```bash
issuedeck export-project-template myapp --config server.toml
issuedeck export-project-template myapp \
  --config server.toml \
  --template-key team-delivery \
  --name "Team delivery" \
  --out ./project-templates/team-delivery.toml
```

The command copies project kinds, statuses, branches, ship exemptions, and
custom fields into the local template-pack format. Use `--dry-run` to preview
the TOML and `--force` to replace an existing output file.

## Built-In Templates

| Template | Best for | Includes | Custom fields |
| --- | --- | --- | --- |
| Basic issue deck | Demos and lightweight personal backlogs | Feature, Bug, Improvement; Proposed, In Progress, Done, Won't Fix; Main branch | Priority, Source URL |
| Agent workflow | Human plus AI coding-agent triage | Feature, Bug, Improvement, Task; Proposed, In Progress, Blocked, Ready to Ship, Done, Won't Fix; Main branch | Priority, Estimate, Customer impact, Source URL |
| Software team | Broader product delivery boards | Epic, Feature, Bug, Chore; Backlog, Ready, In Progress, Review, Done, Won't Fix; Main and Release branches | Priority, Estimate, Component, Source URL |

## Notes

- Project keys must stay lowercase and URL-safe, for example `acme-web`.
- The selected template only affects the initial TOML. Existing projects are
  never rewritten by changing templates later.
- Statuses with `requires_ship = true` still follow normal IssueDeck ship
  rules.
