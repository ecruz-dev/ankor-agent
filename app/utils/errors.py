"""Application error types and handlers."""

from __future__ import annotations

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Raised for expected application-level failures."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "application_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

    def to_response(self) -> dict[str, str]:
        """Serialize the error for API responses."""
        return {"error": self.error_code, "message": self.message}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Render application errors as JSON responses."""
    logger.warning(
        "Application error",
        extra={"error_code": exc.error_code, "status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_response())
