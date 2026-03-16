from __future__ import annotations

from app.services.teamspeak.query_codec import decode_value, encode_value, parse_kv_segment


def test_codec_roundtrip() -> None:
    value = "Привет / test | demo"
    encoded = encode_value(value)
    decoded = decode_value(encoded)
    assert decoded == value


def test_parse_kv_segment() -> None:
    parsed = parse_kv_segment("clid=4 client_nickname=Test\\sUser")
    assert parsed["clid"] == "4"
    assert parsed["client_nickname"] == "Test User"
