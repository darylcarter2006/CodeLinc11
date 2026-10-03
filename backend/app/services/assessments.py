"""Saved assessments and nonpersistent what-if scenarios."""

from __future__ import annotations

from typing import Any

from app.calculators.registry import get_policy
from app.contracts.requests import ScenarioOverrides, ScenarioRequest
from app.contracts.responses import (
    AssessmentResponse,
    GapRange,
    ScenarioResponse,
    ScenarioResult,
)
from app.domain.profile import Profile, ProfileValue, Source
from app.domain.records import AssessmentRecord, SessionRecord
from app.errors import NotFound, StaleRevision
from app.repositories.base import SessionRepository
from app.security.tokens import new_id
from app.services.presenters import to_assessment_response, to_preview
from app.services.sessions import Clock


def apply_overrides(profile: Profile, overrides: ScenarioOverrides) -> Profile:
    """Return a modified copy; the canonical profile is never touched."""
    changes: dict[str, Any] = {}
    for name in overrides.model_fields_set - {"exclude_employer_coverage"}:
        value = getattr(overrides, name)
        if value is not None:
            changes[name] = ProfileValue[Any](value=value, source=Source.EDITED, confirmed=True)
    if overrides.exclude_employer_coverage:
        changes["employer_coverage"] = ProfileValue[Any](
            value=0, source=Source.EDITED, confirmed=True
        )
    return profile.with_fields(changes)


class AssessmentService:
    def __init__(self, repo: SessionRepository, clock: Clock) -> None:
        self._repo = repo
        self._clock = clock

    async def save(
        self, session: SessionRecord, expected_revision: int | None
    ) -> AssessmentResponse:
        if expected_revision is not None and expected_revision != session.revision:
            raise StaleRevision(current_revision=session.revision)
        record = AssessmentRecord(
            id=new_id("asm"),
            session_id=session.id,
            profile_revision=session.revision,
            profile_snapshot=session.profile,
            result=get_policy().calculate(session.profile),
            created_at=self._clock(),
        )
        await self._repo.add_assessment(record)
        return to_assessment_response(record, session)

    async def latest(self, session: SessionRecord) -> AssessmentResponse:
        record = await self._repo.get_latest_assessment(session.id)
        if record is None:
            raise NotFound("No assessment has been saved for this session yet.")
        return to_assessment_response(record, session)

    def scenarios(self, session: SessionRecord, request: ScenarioRequest) -> ScenarioResponse:
        if request.base_revision != session.revision:
            raise StaleRevision(current_revision=session.revision)
        policy = get_policy()
        base = to_preview(policy.calculate(session.profile))
        results = [
            ScenarioResult(
                name=spec.name,
                overrides=spec.overrides.model_dump(exclude_unset=True),
                result=to_preview(
                    policy.calculate(apply_overrides(session.profile, spec.overrides))
                ),
            )
            for spec in request.scenarios
        ]
        gaps = [
            preview.additional_coverage_gap
            for preview in [base, *(r.result for r in results)]
            if preview.additional_coverage_gap is not None
        ]
        return ScenarioResponse(
            base_revision=session.revision,
            base=base,
            scenarios=results,
            range=GapRange(low=min(gaps), high=max(gaps)) if gaps else None,
        )
