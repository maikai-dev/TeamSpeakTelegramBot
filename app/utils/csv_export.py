from __future__ import annotations

import csv
import io
from collections.abc import Iterable


def to_csv_bytes(rows: Iterable[dict[str, object]]) -> bytes:
    rows_list = list(rows)
    if not rows_list:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows_list[0].keys()))
    writer.writeheader()
    writer.writerows(rows_list)
    return buf.getvalue().encode("utf-8")
