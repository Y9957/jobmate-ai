from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.db import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health(response: Response, session: Session = Depends(get_session)) -> HealthResponse:
    """Liveness plus a real database round trip. Returns 503 when the database is unreachable."""
    try:
        session.execute(text("SELECT 1"))
        db_state = "ok"
    except SQLAlchemyError:
        db_state = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="ok" if db_state == "ok" else "degraded", database=db_state, version=__version__)
