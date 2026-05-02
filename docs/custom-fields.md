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

Filter REST list responses with repeated `custom_field=FIELD=VALUE` query
parameters:

```bash
curl \
  -H "Authorization: Bearer $ISSUEDECK_API_TOKEN" \
  "http://127.0.0.1:8775/api/v1/projects/example/items?custom_field=priority=high"
```

## Dashboard

The item create/edit form renders configured custom fields automatically.
Submitted values appear on the item detail page. The list filter panel also
renders configured custom fields, so saved dashboard filters can include values
such as `priority=high` or `customer_impact=true`.

## Imports

CSV and JSON imports can map source columns or object keys into project custom
fields with `custom.<field_key>=alias` field aliases:

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --field-alias custom.priority=Priority \
  --field-alias custom.estimate=Points
```

The same alias syntax is available in the dashboard file-import form. Markdown
task-list imports do not map custom fields because task lines do not carry
structured per-field metadata.
