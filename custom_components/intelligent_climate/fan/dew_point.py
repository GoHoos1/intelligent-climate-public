"""Calculated dew point using the documented Magnus approximation."""

from __future__ import annotations

from math import isfinite, log


def calculate_dew_point_c(
    temperature_c: float | None,
    relative_humidity_pct: float | None,
) -> float | None:
    """Return calculated dew point, or none for invalid/unavailable inputs.

    Constants use the common Magnus approximation over ordinary indoor
    conditions. The value is calculated, never represented as measured.
    """
    if (
        isinstance(temperature_c, bool)
        or not isinstance(temperature_c, int | float)
        or not isfinite(temperature_c)
        or isinstance(relative_humidity_pct, bool)
        or not isinstance(relative_humidity_pct, int | float)
        or not isfinite(relative_humidity_pct)
        or not -100 < temperature_c < 100
        or not 0 < relative_humidity_pct <= 100
    ):
        return None
    coefficient_a = 17.62
    coefficient_b_c = 243.12
    gamma = log(relative_humidity_pct / 100.0) + (
        coefficient_a * temperature_c / (coefficient_b_c + temperature_c)
    )
    result = coefficient_b_c * gamma / (coefficient_a - gamma)
    return round(result, 3)
