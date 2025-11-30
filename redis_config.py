import redis
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Redis connection settings
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Cache expiration times
STATS_CACHE_TTL = 300

# Create Redis client
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True # Automatically decode bytes to strings
    )
except redis.ConnectionError as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None


def get_cache(key: str) -> Optional[str]:
    """
    Get value from Redis cache.
    Returns None if key doesn't exist or Redis is unavailable
    """
    if not redis_client:
        return None
    
    try: 
        value = redis_client.get(key)
        if value: 
            logger.info(f"Cache HIT: {key}")
        else:
            logger.info(f"Cache MISS: {key}")
        return value # type: ignore
    except Exception as e:
        logger.error(f"Redis GET error: {e}")
        return None
    

def set_cache(key: str, value: str, ttl: int = STATS_CACHE_TTL) -> bool:
    """
    Set value in Redis cache with expiration time.
    Returns True if successful, False otherwise.
    """
    if not redis_client:
        return False
    
    try:
        redis_client.setex(key, ttl, value)
        logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Redis SET error: {e}")
        return False
    

def delete_cache(key: str) -> bool:
    """
    Delete value from Redis cache.
    Returns True if successful, False otherwise.
    """
    if not redis_client:
        return False
    
    try:
        redis_client.delete(key)
        logger.info(f"Cache DELETE: {key}")
        return True
    except Exception as e:
        logger.error(f"Redis DELETE error: {e}")
        return False
    

def invalidate_user_cache(user_id: int):
    """Invalidate all cache entries for a user.
    Called when user creates/updates/deletes tasks.
    """
    stats_key = f"stats:user_{user_id}"
    delete_cache(stats_key)
    logger.info(f"Invalidated cache for user_id={user_id}")

    