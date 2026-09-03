"""Score arithmetic: rates and Wilson lower bounds."""

from __future__ import annotations

import math


def wilson_lower(passed: int, total: int, z: float = 1.959963984540054) -> float:
    """Wilson 95% lower bound on a pass rate. 0.0 for an empty denominator."""
    if total <= 0:
        return 0.0
    p = passed / total
    d = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / d)


def rate(passed: int, total: int) -> float:
    return (passed / total) if total else 0.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
