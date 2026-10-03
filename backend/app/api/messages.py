from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AUTH_ERRORS, ContainerDep, SessionDep, error_responses
from app.contracts.requests import MessageRequest
from app.contracts.responses import MessageResponse, MessagesResponse

router = APIRouter(prefix="/sessions/{session_id}/messages", tags=["conversation"])


@router.get("", response_model=MessagesResponse, responses=AUTH_ERRORS)
async def list_messages(session: SessionDep, container: ContainerDep) -> MessagesResponse:
    return await container.conversation.history(session)


@router.post(
    "",
    response_model=MessageResponse,
    responses={**AUTH_ERRORS, **error_responses(409, 422, 429)},
)
async def post_message(
    body: MessageRequest, session: SessionDep, container: ContainerDep
) -> MessageResponse:
    return await container.conversation.handle_turn(session, body)
