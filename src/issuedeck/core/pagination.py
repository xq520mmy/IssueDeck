"""Cursor pagination helpers.

Cursor format: base64url(no padding) of "<updated_at>|<pk>". Small and opaque,
which is what the REST layer wants.

All list endpoints sort `(updated_at DESC, pk DESC)`; the decoded cursor is the
last row of the previous page, and the next query is
`WHERE (updated_at, pk) < (:cursor_ts, :cursor_pk)`.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class Cursor:
    updated_at: str
    pk: int


def encode_cursor(updated_at: str, pk: int) -> str:
    raw = f"{updated_at}|{pk}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str) -> Cursor:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as e:
        raise ValueError(f"invalid cursor: {e}") from e
    if "|" not in raw:
        raise ValueError("invalid cursor: missing separator")
    ts, pk_str = raw.rsplit("|", 1)
    try:
        pk = int(pk_str)
    except ValueError as e:
        raise ValueError(f"invalid cursor: pk not int: {e}") from e
    return Cursor(updated_at=ts, pk=pk)
