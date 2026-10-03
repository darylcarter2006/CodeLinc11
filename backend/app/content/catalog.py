"""Educational copy served to the frontend.

Every entry here must be reviewed before a customer-facing launch. Never generate this
text with the model, and never add a URL that has not been checked by a person.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

CONTENT_VERSION = "draft-1"
REVIEW_STATUS = "pending_compliance_review"

DISCLAIMER = "Planning estimate, not a quote or a product recommendation."

LIMITATIONS: tuple[str, ...] = (
    "Inflation and investment returns are not modeled.",
    "Employer coverage is not guaranteed to continue if employment changes.",
    "Product features and availability vary by state and insurer.",
    "All amounts are estimates you entered.",
)


class CoverageType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    summary: str
    points: tuple[str, ...]


class Resource(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    summary: str
    url: str
    source_owner: str


COVERAGE_TYPES: tuple[CoverageType, ...] = (
    CoverageType(
        id="term",
        title="Term life insurance",
        summary="Coverage for a set period, such as 10, 20, or 30 years.",
        points=(
            "Pays a death benefit only if the insured person dies during the term.",
            "Usually costs less than permanent coverage for the same death benefit.",
            "Often used to cover needs with an end date, such as raising children "
            "or paying off a mortgage.",
        ),
    ),
    CoverageType(
        id="permanent",
        title="Permanent life insurance",
        summary="Coverage intended to last for the insured person's whole life.",
        points=(
            "Whole life is one type of permanent insurance; universal life is another.",
            "Many permanent policies include features beyond the death benefit, "
            "such as cash value.",
            "Usually costs more than term coverage for the same death benefit.",
        ),
    ),
)

# Add only links that a person has verified. Empty until then.
RESOURCES: tuple[Resource, ...] = ()
