import logging

from fastapi import APIRouter

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> dict[str, str]:
    logger.info("Handling /health request")
    res = {
        "status": "healthy",
        "message": "Local Voice Assistant API is running",
    }
    logger.info("Sending /health response: %s", res)
    return res
