from issuedeck.features.items.external_links import infer_external_link
from issuedeck.features.items.schemas import ExternalLinkInput


def test_infers_github_issue_url():
    link = infer_external_link("https://github.com/example/repo/issues/42?from=docs")

    assert link == {
        "link_type": "github_issue",
        "label": "Issue #42",
        "url": "https://github.com/example/repo/issues/42",
    }


def test_infers_github_pr_url():
    link = infer_external_link("http://www.github.com/example/repo/pull/12/")

    assert link == {
        "link_type": "github_pr",
        "label": "PR #12",
        "url": "https://github.com/example/repo/pull/12",
    }


def test_infers_github_commit_url():
    link = infer_external_link("https://github.com/example/repo/commit/abc1234def")

    assert link == {
        "link_type": "github_commit",
        "label": "Commit abc1234",
        "url": "https://github.com/example/repo/commit/abc1234def",
    }


def test_non_github_url_defaults_to_other():
    link = infer_external_link("https://example.com/review/42")

    assert link == {
        "link_type": "other",
        "label": None,
        "url": "https://example.com/review/42",
    }


def test_schema_accepts_url_only_and_infers_metadata():
    link = ExternalLinkInput.model_validate({
        "url": "https://github.com/example/repo/pull/77",
    })

    assert link.link_type == "github_pr"
    assert link.label == "PR #77"
    assert link.url == "https://github.com/example/repo/pull/77"


def test_schema_preserves_custom_label():
    link = ExternalLinkInput.model_validate({
        "url": "https://github.com/example/repo/issues/8",
        "label": "Customer report",
    })

    assert link.link_type == "github_issue"
    assert link.label == "Customer report"
