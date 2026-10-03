"""Map domain objects to response contracts."""

from __future__ import annotations

from app.content.catalog import DISCLAIMER, LIMITATIONS
from app.contracts.responses import (
    AssessmentPreview,
    AssessmentResponse,
    LineItemOut,
    MessageOut,
    NextQuestion,
)
from app.domain.assessment import AssessmentBreakdown
from app.domain.profile import Profile
from app.domain.questions import Question
from app.domain.records import AssessmentRecord, MessageRecord, SessionRecord
from app.services.explanation import explain


def to_preview(breakdown: AssessmentBreakdown) -> AssessmentPreview:
    return AssessmentPreview(
        status=breakdown.status,
        calculation_version=breakdown.calculation_version,
        currency=breakdown.currency,
        missing_fields=list(breakdown.missing_fields),
        unresolved_fields=list(breakdown.unresolved_fields),
        annual_shortfall=breakdown.annual_shortfall,
        support_years=breakdown.support_years,
        line_items=[
            LineItemOut(
                code=item.code,
                label=item.label,
                amount=item.amount,
                entered_amount=item.entered_amount,
                display_order=item.display_order,
            )
            for item in breakdown.line_items
        ],
        additional_coverage_gap=breakdown.additional_coverage_gap,
        assumptions=list(breakdown.assumptions),
        warnings=list(breakdown.warnings),
        explanation=explain(breakdown),
        disclaimer=DISCLAIMER,
        limitations=list(LIMITATIONS),
    )


def to_next_question(question: Question | None) -> NextQuestion | None:
    if question is None:
        return None
    return NextQuestion(
        field=question.field,
        text=question.text,
        input_type=question.input_type,
        min=question.min,
        max=question.max,
        allow_unknown=question.allow_unknown,
        review_fields=list(question.review_fields),
    )


def to_assessment_response(record: AssessmentRecord, session: SessionRecord) -> AssessmentResponse:
    is_current = _same_inputs(record.profile_snapshot, session.profile)
    stale_reason = None
    if not is_current:
        stale_reason = (
            f"Profile updated at revision {session.revision}; "
            f"this assessment reflects revision {record.profile_revision}."
        )
    preview = to_preview(record.result)
    return AssessmentResponse(
        **preview.model_dump(),
        id=record.id,
        profile_revision=record.profile_revision,
        is_current=is_current,
        stale_reason=stale_reason,
        created_at=record.created_at,
    )


def to_message_out(message: MessageRecord) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


def _same_inputs(snapshot: Profile, current: Profile) -> bool:
    # Compare profiles rather than revisions: a chat turn that changes nothing bumps the
    # revision but does not make a saved assessment stale.
    return snapshot == current
