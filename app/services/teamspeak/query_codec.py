from __future__ import annotations

ESCAPE_MAP = {
    "\\\\": "\\",
    "\\s": " ",
    "\\p": "|",
    "\\/": "/",
    "\\_": "_",
    "\\a": "\a",
    "\\b": "\b",
    "\\f": "\f",
    "\\n": "\n",
    "\\r": "\r",
    "\\t": "\t",
    "\\v": "\v",
}


def decode_value(raw: str) -> str:
    text = raw
    # Важно: \\\\ нужно обрабатывать последним
    for pattern, repl in [item for item in ESCAPE_MAP.items() if item[0] != "\\\\"]:
        text = text.replace(pattern, repl)
    text = text.replace("\\\\", "\\")
    return text


def encode_value(raw: str) -> str:
    text = raw
    replacements = [
        ("\\", "\\\\"),
        (" ", "\\s"),
        ("|", "\\p"),
        ("/", "\\/"),
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def parse_kv_segment(segment: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if not segment:
        return result
    for token in segment.split(" "):
        if not token:
            continue
        if "=" not in token:
            result[token] = ""
            continue
        key, value = token.split("=", 1)
        result[key] = decode_value(value)
    return result


def parse_data_lines(lines: list[str]) -> list[dict[str, str]]:
    combined = "|".join(line.strip() for line in lines if line.strip())
    if not combined:
        return []
    chunks = [chunk for chunk in combined.split("|") if chunk]
    return [parse_kv_segment(chunk) for chunk in chunks]


def parse_error_line(line: str) -> tuple[int, str]:
    values = parse_kv_segment(line.replace("error ", "", 1))
    return int(values.get("id", "0")), values.get("msg", "ok")
