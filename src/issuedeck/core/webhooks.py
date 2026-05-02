"""Signed lifecycle webhook delivery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel

from issuedeck.core.config import NotificationConfig, WebhookConfig, WebhookEvent

log = logging.getLogger("issuedeck.webhooks")

SleepFn = Callable[[float], Awaitable[Any]]


def build_webhook_payload(
    event: WebhookEvent,
    item: BaseModel,
    *,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    return {
        "event": event,
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        "item": item.model_dump(mode="json"),
    }


def _notification_event_label(event: WebhookEvent) -> str:
    return {
        "item.created": "created",
        "item.updated": "updated",
        "item.shipped": "shipped",
        "item.deleted": "deleted",
        "item.restored": "restored",
    }[event]


def _compact_text(value: Any, *, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."


def build_notification_text(event: WebhookEvent, item: BaseModel) -> str:
    data = item.model_dump(mode="json")
    item_id = _compact_text(data.get("local_id") or "item", limit=80)
    title = _compact_text(data.get("title") or "Untitled item")
    status = _compact_text(data.get("status"), limit=80)
    kind = _compact_text(data.get("kind"), limit=80)
    project = _compact_text(data.get("project_key"), limit=80)
    verb = _notification_event_label(event)

    metadata = [
        value
        for value in (
            f"project: {project}" if project else "",
            f"kind: {kind}" if kind else "",
            f"status: {status}" if status else "",
        )
        if value
    ]
    details = f"\n{', '.join(metadata)}" if metadata else ""
    return _compact_text(f"IssueDeck: {item_id} {verb} - {title}{details}", limit=1900)


def build_notification_payload(
    notification: NotificationConfig,
    event: WebhookEvent,
    item: BaseModel,
) -> dict[str, Any]:
    text = build_notification_text(event, item)
    if notification.provider == "slack":
        return {"text": text}
    if notification.provider == "discord":
        return {
            "content": text,
            "allowed_mentions": {"parse": []},
        }
    raise ValueError(f"unsupported notification provider: {notification.provider}")


def encode_webhook_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def webhook_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_webhook_headers(
    webhook: WebhookConfig,
    event: WebhookEvent,
    body: bytes,
    *,
    delivery_id: str | None = None,
) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": "IssueDeck",
        "X-IssueDeck-Event": event,
        "X-IssueDeck-Delivery": delivery_id or str(uuid4()),
        "X-IssueDeck-Signature": webhook_signature(
            webhook.secret.get_secret_value(),
            body,
        ),
    }


async def deliver_webhook(
    webhook: WebhookConfig,
    payload: dict[str, Any],
    event: WebhookEvent,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: SleepFn = asyncio.sleep,
) -> bool:
    body = encode_webhook_body(payload)
    headers = build_webhook_headers(webhook, event, body)
    timeout = httpx.Timeout(webhook.timeout_seconds)
    attempts = webhook.retries + 1

    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(webhook.url, content=body, headers=headers)
                if 200 <= response.status_code < 300:
                    return True
                log.warning(
                    "webhook '%s' returned HTTP %s for %s",
                    webhook.name,
                    response.status_code,
                    event,
                )
            except httpx.HTTPError as exc:
                log.warning(
                    "webhook '%s' delivery failed for %s: %s",
                    webhook.name,
                    event,
                    exc.__class__.__name__,
                )

            if attempt < attempts - 1 and webhook.backoff_seconds > 0:
                await sleep(webhook.backoff_seconds * (2**attempt))

    return False


async def deliver_notification(
    notification: NotificationConfig,
    payload: dict[str, Any],
    event: WebhookEvent,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: SleepFn = asyncio.sleep,
) -> bool:
    body = encode_webhook_body(payload)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "IssueDeck",
        "X-IssueDeck-Event": event,
        "X-IssueDeck-Delivery": str(uuid4()),
    }
    timeout = httpx.Timeout(notification.timeout_seconds)
    attempts = notification.retries + 1

    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(
                    notification.url.get_secret_value(),
                    content=body,
                    headers=headers,
                )
                if 200 <= response.status_code < 300:
                    return True
                log.warning(
                    "%s notification '%s' returned HTTP %s for %s",
                    notification.provider,
                    notification.name,
                    response.status_code,
                    event,
                )
            except httpx.HTTPError as exc:
                log.warning(
                    "%s notification '%s' delivery failed for %s: %s",
                    notification.provider,
                    notification.name,
                    event,
                    exc.__class__.__name__,
                )

            if attempt < attempts - 1 and notification.backoff_seconds > 0:
                await sleep(notification.backoff_seconds * (2**attempt))

    return False


class WebhookDispatcher:
    def __init__(
        self,
        webhooks: list[WebhookConfig],
        notifications: list[NotificationConfig] | None = None,
    ) -> None:
        self._webhooks = webhooks
        self._notifications = notifications or []

    def emit(self, event: WebhookEvent, item: BaseModel) -> None:
        targets = [webhook for webhook in self._webhooks if event in webhook.events]
        notification_targets = [
            notification
            for notification in self._notifications
            if event in notification.events
        ]
        if not targets and not notification_targets:
            return
        webhook_payload = build_webhook_payload(event, item)
        for webhook in targets:
            asyncio.create_task(self._deliver_safe(webhook, webhook_payload, event))
        for notification in notification_targets:
            payload = build_notification_payload(notification, event, item)
            asyncio.create_task(
                self._deliver_notification_safe(notification, payload, event)
            )

    async def _deliver_safe(
        self,
        webhook: WebhookConfig,
        payload: dict[str, Any],
        event: WebhookEvent,
    ) -> None:
        delivered = await deliver_webhook(webhook, payload, event)
        if not delivered:
            log.warning("webhook '%s' exhausted retries for %s", webhook.name, event)

    async def _deliver_notification_safe(
        self,
        notification: NotificationConfig,
        payload: dict[str, Any],
        event: WebhookEvent,
    ) -> None:
        delivered = await deliver_notification(notification, payload, event)
        if not delivered:
            log.warning(
                "%s notification '%s' exhausted retries for %s",
                notification.provider,
                notification.name,
                event,
            )
