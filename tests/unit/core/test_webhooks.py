import hmac
import json
import smtplib

import httpx

from issuedeck.core.config import EmailNotificationConfig, NotificationConfig, WebhookConfig
from issuedeck.core.webhooks import (
    build_email_notification_message,
    build_notification_payload,
    build_webhook_headers,
    build_webhook_payload,
    deliver_email_notification,
    deliver_notification,
    deliver_webhook,
    encode_webhook_body,
    webhook_signature,
)
from issuedeck.features.items.schemas import ItemSummary


def _summary() -> ItemSummary:
    return ItemSummary(
        project_key="example",
        local_id="FEAT-0001",
        kind="feature",
        status="proposed",
        title="Webhook payload",
        body_preview="Short body",
        tags=["integration"],
        applies_to=["main"],
        external_links=[],
        created_at="2026-04-29T00:00:00+00:00",
        updated_at="2026-04-29T00:00:00+00:00",
    )


def test_webhook_payload_shape_is_stable():
    payload = build_webhook_payload(
        "item.created",
        _summary(),
        occurred_at="2026-04-29T01:00:00+00:00",
    )

    assert payload["event"] == "item.created"
    assert payload["occurred_at"] == "2026-04-29T01:00:00+00:00"
    assert payload["item"]["project_key"] == "example"
    assert payload["item"]["local_id"] == "FEAT-0001"
    assert payload["item"]["tags"] == ["integration"]


def test_webhook_signature_uses_hmac_sha256():
    body = b'{"event":"item.created"}'
    expected = hmac.digest(b"shared-secret", body, "sha256").hex()

    assert webhook_signature("shared-secret", body) == f"sha256={expected}"


def test_webhook_headers_include_delivery_context():
    webhook = WebhookConfig(
        name="automation",
        url="https://example.com/hooks/issuedeck",
        secret="shared-secret",
    )
    body = encode_webhook_body({"event": "item.created"})

    headers = build_webhook_headers(
        webhook,
        "item.created",
        body,
        delivery_id="delivery-123",
    )

    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "IssueDeck"
    assert headers["X-IssueDeck-Event"] == "item.created"
    assert headers["X-IssueDeck-Delivery"] == "delivery-123"
    assert headers["X-IssueDeck-Signature"].startswith("sha256=")


async def test_deliver_webhook_retries_until_success():
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(500)
        return httpx.Response(204)

    webhook = WebhookConfig(
        name="automation",
        url="https://example.com/hooks/issuedeck",
        secret="shared-secret",
        retries=1,
        backoff_seconds=0,
    )

    delivered = await deliver_webhook(
        webhook,
        build_webhook_payload("item.updated", _summary()),
        "item.updated",
        transport=httpx.MockTransport(handler),
    )

    assert delivered is True
    assert len(seen) == 2
    assert seen[0].headers["X-IssueDeck-Event"] == "item.updated"
    assert seen[1].headers["X-IssueDeck-Signature"].startswith("sha256=")


def test_slack_notification_payload_uses_text():
    notification = NotificationConfig(
        name="team-alerts",
        provider="slack",
        url="https://hooks.slack.com/services/T000/B000/secret",
    )

    payload = build_notification_payload(notification, "item.created", _summary())

    assert set(payload) == {"text"}
    assert payload["text"].startswith("IssueDeck: FEAT-0001 created")
    assert "Webhook payload" in payload["text"]
    assert "project: example" in payload["text"]


def test_discord_notification_payload_disables_mentions():
    notification = NotificationConfig(
        name="team-alerts",
        provider="discord",
        url="https://discord.com/api/webhooks/123/secret",
    )

    payload = build_notification_payload(notification, "item.shipped", _summary())

    assert payload["content"].startswith("IssueDeck: FEAT-0001 shipped")
    assert payload["allowed_mentions"] == {"parse": []}


async def test_deliver_notification_retries_until_success():
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(500)
        return httpx.Response(204)

    notification = NotificationConfig(
        name="team-alerts",
        provider="discord",
        url="https://discord.com/api/webhooks/123/secret",
        retries=1,
        backoff_seconds=0,
    )

    delivered = await deliver_notification(
        notification,
        build_notification_payload(notification, "item.updated", _summary()),
        "item.updated",
        transport=httpx.MockTransport(handler),
    )

    assert delivered is True
    assert len(seen) == 2
    assert seen[0].headers["X-IssueDeck-Event"] == "item.updated"
    assert json.loads(seen[1].content)["allowed_mentions"] == {"parse": []}


def test_email_notification_message_shape():
    notification = EmailNotificationConfig(
        name="ops-inbox",
        smtp_host="smtp.example.com",
        from_email="issuebot@example.com",
        to_emails=["ops@example.com", "dev@example.com"],
        subject_prefix="[IssueDeck Ops]",
    )

    message = build_email_notification_message(
        notification,
        "item.shipped",
        _summary(),
    )

    assert message["Subject"].startswith("[IssueDeck Ops] FEAT-0001 shipped")
    assert message["From"] == "issuebot@example.com"
    assert message["To"] == "ops@example.com, dev@example.com"
    assert message["X-IssueDeck-Event"] == "item.shipped"
    assert "Webhook payload" in message.get_content()


async def test_deliver_email_notification_retries_until_success():
    attempts: list[object] = []
    sent_messages = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, *, timeout: float):
            attempts.append((host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def starttls(self):
            attempts.append("starttls")

        def login(self, username: str, password: str):
            attempts.append(("login", username, password))

        def send_message(self, message):
            sent_messages.append(message)
            if len(sent_messages) == 1:
                raise smtplib.SMTPException("temporary failure")

    notification = EmailNotificationConfig(
        name="ops-inbox",
        smtp_host="smtp.example.com",
        username="issuebot",
        password="smtp-secret",
        from_email="issuebot@example.com",
        to_emails=["ops@example.com"],
        retries=1,
        backoff_seconds=0,
    )

    delivered = await deliver_email_notification(
        notification,
        "item.updated",
        _summary(),
        smtp_factory=FakeSmtp,
    )

    assert delivered is True
    assert len(sent_messages) == 2
    assert attempts.count("starttls") == 2
    assert ("login", "issuebot", "smtp-secret") in attempts
    assert sent_messages[1]["X-IssueDeck-Event"] == "item.updated"
