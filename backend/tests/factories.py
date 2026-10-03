from __future__ import annotations

from typing import Any

from app.domain.profile import Profile, Source


def make_profile(
    *, confirmed: bool = True, source: Source = Source.EDITED, **values: Any
) -> Profile:
    """Build a profile from plain values; ``None`` means "answered: unknown"."""
    flags = values.pop("assumption_flags", None)
    data: dict[str, Any] = {
        name: {"value": value, "source": source, "confirmed": confirmed}
        for name, value in values.items()
    }
    if flags is not None:
        data["assumption_flags"] = flags
    return Profile.model_validate(data)


EXAMPLE_VALUES: dict[str, Any] = {
    "annual_support_need": 80_000,
    "annual_survivor_contribution": 20_000,
    "support_years": 15,
    "one_time_expenses": [
        {"id": "education-1", "label": "Education", "category": "education", "amount": 50_000}
    ],
    "available_assets": 30_000,
    "personal_coverage": 100_000,
    "employer_coverage": 150_000,
    "assumption_flags": {"education_in_annual_support": False},
}

# The same example as a PATCH body: every question answered, all values confirmed.
EXAMPLE_PATCH: dict[str, Any] = {**EXAMPLE_VALUES, "dependents_count": 2, "budget_monthly": None}
