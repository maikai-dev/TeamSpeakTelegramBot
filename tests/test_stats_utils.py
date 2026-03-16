from __future__ import annotations

from app.utils.charts import bar_chart, heatmap_grid
from app.utils.formatting import humanize_seconds


def test_bar_chart_has_bars() -> None:
    chart = bar_chart([("A", 10), ("B", 5)])
    assert "A" in chart
    assert "10" in chart


def test_heatmap_grid_shape() -> None:
    text = heatmap_grid([(1, 10, 5), (1, 11, 9), (2, 10, 2)])
    assert "Пн" in text
    assert "Вт" in text


def test_humanize_seconds() -> None:
    assert humanize_seconds(65) == "1м 5с"
    assert "1ч" in humanize_seconds(3665)
