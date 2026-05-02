import pytest

from issuedeck.core.errors import ConfigError
from issuedeck.features.projects.project_templates import (
    load_project_templates,
    render_project_toml,
)


def test_load_project_templates_from_directory(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "research.toml").write_text(
        "\n".join([
            'key = "research"',
            'name = "Research lab"',
            'description = "Discovery work before delivery."',
            "",
            "[[kinds]]",
            'key = "question"',
            'label = "Question"',
            'prefix = "QST"',
            "",
            "[[statuses]]",
            'key = "open"',
            'label = "Open"',
            "",
            "[[statuses]]",
            'key = "answered"',
            'label = "Answered"',
            "terminal = true",
            "",
        ]),
        encoding="utf-8",
    )

    templates = load_project_templates(templates_dir)

    assert len(templates) == 1
    assert templates[0].key == "research"
    assert templates[0].name_i18n == "Research lab"
    assert templates[0].kind_labels == ("Question",)
    assert templates[0].status_labels == ("Open", "Answered")


def test_loaded_template_renders_valid_project_toml(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "delivery.toml").write_text(
        "\n".join([
            'key = "delivery"',
            'name = "Delivery board"',
            'description = "Feature delivery with releases."',
            "",
            "[custom_fields.priority]",
            'label = "Priority"',
            'type = "select"',
            'options = ["low", "high"]',
            "required = true",
            "",
            "[[kinds]]",
            'key = "feature"',
            'label = "Feature"',
            'prefix = "FEAT"',
            "",
            "[[statuses]]",
            'key = "backlog"',
            'label = "Backlog"',
            "",
            "[[statuses]]",
            'key = "done"',
            'label = "Done"',
            "terminal = true",
            "requires_ship = true",
            "",
            "[[branches]]",
            'key = "main"',
            'label = "Main"',
            "",
        ]),
        encoding="utf-8",
    )

    template = load_project_templates(templates_dir)[0]
    rendered = render_project_toml(
        key="delivery",
        name="Delivery",
        description="Team delivery board.",
        template=template,
    )

    assert "[kinds.feature]" in rendered
    assert "[statuses.done]" in rendered
    assert "requires_ship = true" in rendered
    assert "[[branches]]" in rendered
    assert "[custom_fields.priority]" in rendered
    assert 'options = ["low", "high"]' in rendered


def test_load_project_templates_rejects_builtin_key_collision(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "basic.toml").write_text(
        "\n".join([
            'key = "basic"',
            'name = "Shadow basic"',
            "",
            "[[kinds]]",
            'key = "task"',
            'label = "Task"',
            'prefix = "TASK"',
            "",
            "[[statuses]]",
            'key = "open"',
            'label = "Open"',
            "",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="duplicate project template key"):
        load_project_templates(templates_dir)


def test_load_project_templates_rejects_requires_ship_without_branch(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "bad.toml").write_text(
        "\n".join([
            'key = "bad"',
            'name = "Bad template"',
            "",
            "[[kinds]]",
            'key = "feature"',
            'label = "Feature"',
            'prefix = "FEAT"',
            "",
            "[[statuses]]",
            'key = "done"',
            'label = "Done"',
            "terminal = true",
            "requires_ship = true",
            "",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="requires_ship"):
        load_project_templates(templates_dir)
