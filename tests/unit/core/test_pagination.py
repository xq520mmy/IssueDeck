from datetime import UTC, datetime

import pytest

from issuedeck.core.pagination import Cursor, decode_cursor, encode_cursor


def test_encode_decode_roundtrip():
    ts = "2026-04-11T12:34:56+00:00"
    pk = 1234
    token = encode_cursor(ts, pk)
    assert isinstance(token, str)
    assert "=" not in token  # urlsafe-no-padding
    back = decode_cursor(token)
    assert back == Cursor(updated_at=ts, pk=pk)


def test_decode_invalid_raises_value_error():
    with pytest.raises(ValueError):
        decode_cursor("not-a-cursor")


def test_decode_tampered_raises_value_error():
    import base64
    junk = base64.urlsafe_b64encode(b"hello").decode().rstrip("=")
    with pytest.raises(ValueError):
        decode_cursor(junk)


def test_cursor_roundtrip_with_timezone_aware_iso():
    dt = datetime(2026, 4, 11, 12, 34, 56, tzinfo=UTC).isoformat()
    token = encode_cursor(dt, 42)
    assert decode_cursor(token).updated_at == dt
