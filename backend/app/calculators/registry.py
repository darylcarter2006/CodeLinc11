"""Lookup of published calculation policies by version string."""

from __future__ import annotations

from app.calculators.base import CalculationPolicy
from app.calculators.v1 import NeedsV1

_POLICIES: dict[str, CalculationPolicy] = {policy.version: policy for policy in [NeedsV1()]}

CURRENT_VERSION = NeedsV1.version


def get_policy(version: str = CURRENT_VERSION) -> CalculationPolicy:
    try:
        return _POLICIES[version]
    except KeyError:
        raise ValueError(f"Unknown calculation version: {version}") from None
