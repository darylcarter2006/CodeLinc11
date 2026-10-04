from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import ContainerDep, error_responses
from app.contracts.ai import ChatRequest, ExtractRequest, ExtractResponse

router = APIRouter(prefix="/ai", tags=["ai"])


def rate_limit(request: Request, container: ContainerDep) -> None:
    client = request.client.host if request.client else "unknown"
    container.ai_limiter.check(client)
    container.ai_global_limiter.check("all-clients")


AI_ERRORS = error_responses(422, 429, 502, 503)


@router.post(
    "/extract",
    response_model=ExtractResponse,
    responses=AI_ERRORS,
    dependencies=[Depends(rate_limit)],
)
async def extract(body: ExtractRequest, container: ContainerDep) -> ExtractResponse:
    """Pull profile fields from one onboarding answer. Only validated values come back."""
    return await container.compass_ai.extract(body)


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/plain": {}}}, **AI_ERRORS},
    dependencies=[Depends(rate_limit)],
)
async def chat(body: ChatRequest, container: ContainerDep) -> StreamingResponse:
    """Stream a plain-text answer grounded in the profile's server-computed numbers."""
    stream = await container.compass_ai.chat(body)
    return StreamingResponse(
        stream,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
