"""Health endpoints for the ANKOR voice service."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a basic health status."""
    return {"status": "ok"}
