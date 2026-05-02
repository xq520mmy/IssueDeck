import pytest

from issuedeck.core.config import (
    CustomFieldConfig,
    KindConfig,
    ProjectConfig,
    StatusConfig,
)
from issuedeck.core.errors import InvalidCustomField
from issuedeck.features.items.custom_fields import (
    CustomFieldFilter,
    normalize_custom_field_filters,
    parse_custom_field_filter_options,
)


def _project() -> ProjectConfig:
    project = ProjectConfig(
        key="test",
        name="Test",
        kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
        statuses={"proposed": StatusConfig(label="Proposed")},
    )
    project.custom_fields = {
        "priority": CustomFieldConfig(
            label="Priority",
            type="select",
            options=["low", "high"],
        ),
        "estimate": CustomFieldConfig(label="Estimate", type="number"),
        "source_url": CustomFieldConfig(label="Source URL", type="url"),
    }
    return project


def test_parse_custom_field_filter_options_supports_range_and_presence():
    parsed = parse_custom_field_filter_options(
        _project(),
        ["priority=high", "estimate>=3", "estimate<=8", "source_url:missing"],
    )

    assert parsed == {
        "priority": "high",
        "estimate__min": "3",
        "estimate__max": "8",
        "source_url__presence": "missing",
    }


def test_normalize_custom_field_filters_returns_typed_filters():
    filters = normalize_custom_field_filters(
        _project(),
        {
            "priority": "high",
            "estimate__min": "3",
            "estimate__max": "8",
            "source_url__presence": "present",
        },
    )

    assert filters == [
        CustomFieldFilter(key="priority", op="eq", value="high"),
        CustomFieldFilter(key="estimate", op="gte", value=3),
        CustomFieldFilter(key="estimate", op="lte", value=8),
        CustomFieldFilter(key="source_url", op="present"),
    ]


def test_normalize_custom_field_filters_rejects_range_on_non_number_field():
    with pytest.raises(InvalidCustomField):
        normalize_custom_field_filters(_project(), {"priority__min": "low"})
