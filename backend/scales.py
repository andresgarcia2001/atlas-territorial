"""Stable analytical scale helpers shared by API and map delivery."""

from dataclasses import dataclass
import math
from typing import Sequence


@dataclass(frozen=True)
class IndicatorScale:
    indicator: str
    level: str
    year: int
    domain_min: float
    domain_max: float
    transform: str
    method: str


def compute_scale(indicator: str, level: str, year: int, values: Sequence[float]) -> IndicatorScale:
    if indicator.startswith("porcentaje_"):
        return IndicatorScale(indicator, level, year, 0.0, 100.0, "linear", "fixed_percentage")

    numeric_values = list(values)
    minimum = min(numeric_values, default=0.0)
    maximum = max(numeric_values, default=1.0)
    return IndicatorScale(
        indicator,
        level,
        year,
        min(0.0, minimum),
        max(1.0, maximum),
        "sqrt",
        "global_min_max",
    )


def compute_ratio(value: float | None, scale: IndicatorScale) -> float | None:
    if value is None:
        return None

    if scale.domain_min == scale.domain_max:
        return 0.5

    raw_ratio = (value - scale.domain_min) / (scale.domain_max - scale.domain_min)
    clamped_ratio = max(0.0, min(1.0, raw_ratio))
    return math.sqrt(clamped_ratio) if scale.transform == "sqrt" else clamped_ratio
