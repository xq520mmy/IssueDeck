# Custom Fields

Projects can define lightweight custom fields for extra item metadata such as
priority, estimate, customer impact, or source URL. Values are stored with each
item, returned by the REST API, shown in the dashboard, and included in Markdown
exports and audit bundles.

## Configure

Add `[custom_fields.<key>]` blocks to a project TOML:

```toml
[custom_fields.priority]
label = "Priority"
type = "select"
required = true
options = ["low", "medium", "high"]

[custom_fields.estimate]
label = "Estimate"
type = "number"

[custom_fields.customer_impact]
label = "Customer impact"
type = "checkbox"

[custom_fields.source_url]
label = "Source URL"
type = "url"
```

Field keys must start with a lowercase letter and may contain lowercase letters,
numbers, `-`, or `_`.

Supported field types:

- `text`
- `number`
- `checkbox`
- `select`
- `url`

`select` fields must define `options`. Required fields must be present when an
item is created or updated through the API.

## API

Create or update items with `custom_fields`:

```json
{
  "kind": "feature",
  "title": "Add onboarding report",
  "custom_fields": {
    "priority": "high",
    "estimate": 3,
    "customer_impact": true
  }
}
```

Unknown fields, invalid select options, and non-numeric number values are
rejected with `invalid_custom_field`.

## Dashboard

The item create/edit form renders configured custom fields automatically.
Submitted values appear on the item detail page.

## Current Scope

Custom fields are stored and exported, but they are not yet searchable, filterable
in list views, or imported from CSV/JSON/Markdown sources.
