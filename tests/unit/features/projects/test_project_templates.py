import pytest

from issuedeck.core.errors import ConfigError
from issuedeck.features.projects.project_templates import (
    install_project_template_pack_example,
    list_project_template_pack_examples,
    list_project_templates,
    load_project_template_from_toml,
    load_project_templates,
    render_project_template_pack_toml,
    render_project_toml,
    validate_project_templates,
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


def test_project_config_renders_valid_template_pack_toml(tmp_path):
    from issuedeck.core.config import load_project_config

    project_path = tmp_path / "project.toml"
    project_path.write_text(
        "\n".join([
            'key = "example"',
            'name = "Example"',
            'description = "Reusable workflow."',
            "",
            "[kinds.feature]",
            'label = "Feature"',
            'prefix = "FEAT"',
            "",
            "[statuses.backlog]",
            'label = "Backlog"',
            "",
            "[statuses.done]",
            'label = "Done"',
            "terminal = true",
            "requires_ship = true",
            "",
            "[[branches]]",
            'key = "main"',
            'label = "Main"',
            "",
            "[ship_rules]",
            'ship_exempt_kinds = ["feature"]',
            "",
            "[custom_fields.priority]",
            'label = "Priority"',
            'type = "select"',
            'options = ["low", "high"]',
            "",
        ]),
        encoding="utf-8",
    )
    project = load_project_config(project_path)

    rendered = render_project_template_pack_toml(
        key="exported",
        name="Exported template",
        description="A reusable workflow.",
        project=project,
    )
    template = load_project_template_from_toml(rendered, source="test")

    assert template.key == "exported"
    assert template.kind_labels == ("Feature",)
    assert template.status_labels == ("Backlog", "Done")
    assert template.branch_labels == ("Main",)
    assert template.ship_exempt_kinds == ("feature",)
    assert template.custom_fields["priority"].options == ["low", "high"]


def test_builtin_templates_include_custom_field_presets():
    templates = {template.key: template for template in list_project_templates()}

    assert templates["basic"].custom_field_labels == ("Priority", "Source URL")
    assert templates["agent"].custom_field_labels == (
        "Priority",
        "Estimate",
        "Customer impact",
        "Source URL",
    )
    assert templates["software"].custom_fields["component"].options == [
        "frontend",
        "backend",
        "api",
        "docs",
        "infra",
    ]


def test_project_template_pack_examples_are_valid():
    examples = list_project_template_pack_examples()

    assert [example.key for example in examples] == ["support", "content", "research"]
    for example in examples:
        template = example.to_project_template()
        assert template.key == example.key
        assert template.kinds
        assert template.statuses
        assert template.custom_fields


def test_install_project_template_pack_example_writes_valid_template(tmp_path):
    templates_dir = tmp_path / "templates"

    path = install_project_template_pack_example("support", templates_dir)

    assert path == templates_dir / "support.toml"
    assert path.exists()
    templates = load_project_templates(templates_dir)
    assert [template.key for template in templates] == ["support"]
    assert "sla_risk" in templates[0].custom_fields


def test_install_project_template_pack_example_rejects_overwrite(tmp_path):
    templates_dir = tmp_path / "templates"
    install_project_template_pack_example("support", templates_dir)

    with pytest.raises(ConfigError, match="already exists"):
        install_project_template_pack_example("support", templates_dir)

    path = install_project_template_pack_example("support", templates_dir, force=True)
    assert path == templates_dir / "support.toml"


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


def test_validate_project_templates_reports_all_files(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "good.toml").write_text(
        "\n".join([
            'key = "support"',
            'name = "Support queue"',
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
        ]),
        encoding="utf-8",
    )
    (templates_dir / "bad.toml").write_text(
        "\n".join([
            'key = "broken"',
            'name = "Broken"',
            "",
            "[[kinds]]",
            'key = "task"',
            'label = "Task"',
            'prefix = "TASK"',
            "",
        ]),
        encoding="utf-8",
    )

    results = validate_project_templates(templates_dir)

    assert [result.path.name for result in results] == ["bad.toml", "good.toml"]
    assert results[0].ok is False
    assert "invalid project template" in results[0].errors[0]
    assert results[1].ok is True
    assert results[1].key == "support"


def test_validate_project_templates_reports_duplicate_builtin_key(tmp_path):
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

    results = validate_project_templates(templates_dir)

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].key == "basic"
    assert results[0].errors == ("duplicate project template key 'basic'",)
