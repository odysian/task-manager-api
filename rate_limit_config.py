import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import logging


logger = logging.getLogger(__name__)

def get_user_id_or_ip(request: Request) -> str:
    """
    Get a unique identifier for rate limiting
    Priority:
    1. User ID (if authenticated)
    2. IP address (if not authenticated)
    """
    # Try to get user from request state (set by auth dependency)
    if hasattr(request.state, "user"):
        user = request.state.user
        identifier = f"user_{user.id}"
        logger.debug(f"Rate limit key: {identifier}")
        return identifier
    
    # Fall back to IP address
    ip = get_remote_address(request)
    identifier = f"ip_{ip}"
    logger.debug(f"Rate limit key: {identifier}")
    return identifier

# Check if we're running tests
TESTING = os.getenv("TESTING", "false").lower() == "true"

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

if TESTING:
    # Create a disabled limiter for tests
    limiter = Limiter(
        key_func=get_user_id_or_ip,
        enabled=False # Disable rate limiting in tests
    )
    logger.info("Rate limiting DISABLED for testing")
else:
    # Create limiter instance for production
    limiter = Limiter(
        key_func=get_user_id_or_ip,
        default_limits=["1000/hour"], # Default limit for all endpoints
        storage_uri=REDIS_URL,
        strategy="fixed-window"
    )
    logger.info("Rate limiting ENABLED with storage: {REDIS_URL}")

