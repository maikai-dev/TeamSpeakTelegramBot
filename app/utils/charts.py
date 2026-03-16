from __future__ import annotations

from collections.abc import Iterable


def bar_chart(items: Iterable[tuple[str, int]], width: int = 18, symbol: str = "-") -> str:
    rows = list(items)
    if not rows:
        return "(нет данных)"
    max_value = max(value for _, value in rows) or 1
    lines: list[str] = []
    for label, value in rows:
        bar_len = int((value / max_value) * width)
        bar = symbol * max(1, bar_len) if value > 0 else ""
        lines.append(f"{label:>12} | {bar} {value}")
    return "\n".join(lines)


def heatmap_grid(points: list[tuple[int, int, int]]) -> str:
    """weekday (0=вс) x hour grid."""
    matrix = [[0 for _ in range(24)] for _ in range(7)]
    for day, hour, value in points:
        if 0 <= day <= 6 and 0 <= hour <= 23:
            matrix[day][hour] = value

    max_value = max((value for row in matrix for value in row), default=0)
    palette = " ???-???-"

    def glyph(value: int) -> str:
        if max_value == 0:
            return palette[0]
        idx = int((value / max_value) * (len(palette) - 1))
        return palette[idx]

    day_names = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    lines = ["      00 06 12 18 23"]
    for day in range(7):
        chunks = "".join(glyph(value) for value in matrix[day])
        lines.append(f"{day_names[day]:>2} | {chunks}")
    return "\n".join(lines)
