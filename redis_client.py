"""
Redis client for caching and pub/sub messaging
"""
import redis
import json
from typing import Any, Optional, Dict, List
from decouple import config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.redis_host = config('REDIS_HOST', default='localhost')
        self.redis_port = config('REDIS_PORT', default=6379, cast=int)
        self.redis_db = config('REDIS_DB', default=0, cast=int)
        self.redis_password = config('REDIS_PASSWORD', default=None)
        
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            password=self.redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # Test connection
        try:
            self.redis_client.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        try:
            return self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in Redis with optional expiration"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            return self.redis_client.set(key, value, ex=expire)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False

    def publish(self, channel: str, message: Any) -> bool:
        """Publish message to Redis channel"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            return bool(self.redis_client.publish(channel, message))
        except Exception as e:
            logger.error(f"Redis PUBLISH error for channel {channel}: {e}")
            return False

    def subscribe(self, channels: List[str]):
        """Subscribe to Redis channels"""
        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(*channels)
            return pubsub
        except Exception as e:
            logger.error(f"Redis SUBSCRIBE error for channels {channels}: {e}")
            return None

    def cache_email_list(self, user_id: str, emails: List[Dict], expire: int = 300):
        """Cache email list for user"""
        key = f"emails:{user_id}"
        return self.set(key, emails, expire)

    def get_cached_email_list(self, user_id: str) -> Optional[List[Dict]]:
        """Get cached email list for user"""
        key = f"emails:{user_id}"
        data = self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    def cache_email_detail(self, email_id: str, email_data: Dict, expire: int = 600):
        """Cache individual email detail"""
        key = f"email:{email_id}"
        return self.set(key, email_data, expire)

    def get_cached_email_detail(self, email_id: str) -> Optional[Dict]:
        """Get cached email detail"""
        key = f"email:{email_id}"
        data = self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    def invalidate_email_cache(self, user_id: str, email_id: Optional[str] = None):
        """Invalidate email cache"""
        self.delete(f"emails:{user_id}")
        if email_id:
            self.delete(f"email:{email_id}")

    def publish_email_event(self, event_type: str, data: Dict):
        """Publish email-related events"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': json.dumps(data.get('timestamp', ''), default=str)
        }
        return self.publish('email_events', event)

    def publish_imap_event(self, event_type: str, data: Dict):
        """Publish IMAP-related events"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': json.dumps(data.get('timestamp', ''), default=str)
        }
        return self.publish('imap_events', event)

# Global Redis client instance
redis_client = RedisClient()
