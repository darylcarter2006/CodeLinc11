from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import ContainerDep
from app.contracts.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: the process is up. Never checks dependencies or reveals config."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def ready(container: ContainerDep) -> HealthResponse | JSONResponse:
    """Readiness: dependencies (the session store) can serve requests."""
    if await container.repo.ping():
        return HealthResponse(status="ok")
    return JSONResponse(status_code=503, content={"status": "unavailable"})
