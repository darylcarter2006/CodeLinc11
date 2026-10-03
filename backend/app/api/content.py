from __future__ import annotations

from fastapi import APIRouter

from app.content.catalog import (
    CONTENT_VERSION,
    COVERAGE_TYPES,
    DISCLAIMER,
    RESOURCES,
    REVIEW_STATUS,
)
from app.contracts.responses import CoverageTypeOut, CoverageTypesResponse, ResourceOut

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/coverage-types", response_model=CoverageTypesResponse)
async def coverage_types() -> CoverageTypesResponse:
    return CoverageTypesResponse(
        content_version=CONTENT_VERSION,
        review_status=REVIEW_STATUS,
        coverage_types=[
            CoverageTypeOut(id=c.id, title=c.title, summary=c.summary, points=list(c.points))
            for c in COVERAGE_TYPES
        ],
        resources=[ResourceOut(**r.model_dump()) for r in RESOURCES],
        disclaimer=DISCLAIMER,
    )
