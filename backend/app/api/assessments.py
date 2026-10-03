from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AUTH_ERRORS, ContainerDep, SessionDep, error_responses
from app.contracts.requests import CreateAssessmentRequest, ScenarioRequest
from app.contracts.responses import AssessmentResponse, ScenarioResponse

router = APIRouter(prefix="/sessions/{session_id}", tags=["assessments"])


@router.post(
    "/assessments",
    status_code=status.HTTP_201_CREATED,
    response_model=AssessmentResponse,
    responses={**AUTH_ERRORS, **error_responses(409)},
)
async def create_assessment(
    session: SessionDep, container: ContainerDep, body: CreateAssessmentRequest | None = None
) -> AssessmentResponse:
    expected = body.expected_revision if body is not None else None
    return await container.assessments.save(session, expected)


@router.get("/assessments/latest", response_model=AssessmentResponse, responses=AUTH_ERRORS)
async def latest_assessment(session: SessionDep, container: ContainerDep) -> AssessmentResponse:
    return await container.assessments.latest(session)


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    responses={**AUTH_ERRORS, **error_responses(409, 422)},
)
async def run_scenarios(
    body: ScenarioRequest, session: SessionDep, container: ContainerDep
) -> ScenarioResponse:
    """What-if calculations. Nothing is saved and the profile is not changed."""
    return container.assessments.scenarios(session, body)
