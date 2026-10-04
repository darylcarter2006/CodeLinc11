"""Simple chat endpoint.

POST /v1/chat — takes a user message and a session token, runs one conversation turn,
and returns just the assistant's reply plus the updated assessment.

This is a convenience wrapper around the full /sessions/{id}/messages flow for clients
that want a simpler API. It auto-increments the revision and generates a client request
ID, so callers do not need to track those themselves.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import AUTH_ERRORS, ContainerDep, SessionDep, error_responses
from app.contracts.requests import MessageRequest
from app.contracts.responses import AssessmentPreview

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=10_000, description="The user's message.")


class ChatResponse(BaseModel):
    """Simplified response for the chat endpoint."""

    reply: str = Field(description="The assistant's reply.")
    done: bool = Field(
        description="True when all questions have been answered and the estimate is ready."
    )
    assessment: AssessmentPreview = Field(
        description="Live insurance needs estimate for the current profile."
    )
    next_question_field: str | None = Field(
        default=None,
        description="The profile field the assistant is currently asking about, or null when done.",
    )


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    responses={**AUTH_ERRORS, **error_responses(409, 422, 429)},
    summary="Send a message and receive an AI reply with the current insurance estimate.",
)
async def chat(
    body: ChatRequest,
    session: SessionDep,
    container: ContainerDep,
) -> ChatResponse:
    """One conversational turn: send a plain message, get a plain reply plus a live estimate.

    The session must already exist (create one via POST /v1/sessions first).
    Revision tracking and idempotency keys are handled automatically.
    """
    request = MessageRequest(
        text=body.message,
        client_request_id=str(uuid.uuid4()).replace("-", ""),
        expected_revision=session.revision,
    )
    result = await container.conversation.handle_turn(session, request)
    return ChatResponse(
        reply=result.assistant_message,
        done=result.next_question is None,
        assessment=result.assessment,
        next_question_field=result.next_question.field if result.next_question else None,
    )
