import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from db_config import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(db_session: Session = Depends(get_db)):
    """
    Health check endpoint for monitoring.
    Returns API status and database connectivity.
    """
    try:
        # Test database connection
        db_session.execute(text("SELECT 1"))
        db_status = "healthy"
        logger.info("Health check passed: database connection OK")
    except Exception as e:
        db_status = "unhealthy"
        logger.error(f"Health check failed: database error - {e}")
    
    return {
        "status": "ok",
        "database": db_status
    }