from supabase import create_client
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os
from functools import lru_cache
import asyncio
from datetime import datetime, timedelta

load_dotenv()

logger = logging.getLogger(__name__)

class BaseService:
    _instance = None
    _supabase_client = None
    _cache = {}
    _cache_ttl = 300  # 5 minutes default TTL

    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id
        self.requires_credits = False
        if not BaseService._supabase_client:
            BaseService._supabase_client = create_client(
                supabase_url=os.getenv('SUPABASE_URL'),
                supabase_key=os.getenv('SUPABASE_ANON_KEY')
            )
        self.supabase = BaseService._supabase_client

    @property
    def cache_key(self) -> str:
        """Generate a cache key based on user_id"""
        return f"user_{self.user_id}" if self.user_id else "global"

    async def get_cached_data(self, key: str) -> Optional[Dict]:
        """Get data from cache if it exists and is not expired"""
        cache_entry = self._cache.get(f"{self.cache_key}_{key}")
        if cache_entry and cache_entry['expires_at'] > datetime.now():
            return cache_entry['data']
        return None

    async def set_cached_data(self, key: str, data: Any, ttl: int = None):
        """Set data in cache with expiration"""
        self._cache[f"{self.cache_key}_{key}"] = {
            'data': data,
            'expires_at': datetime.now() + timedelta(seconds=ttl or self._cache_ttl)
        }

    @lru_cache(maxsize=128)
    async def get_user_profile(self) -> Dict:
        """Get cached user profile data"""
        if not self.user_id:
            return {}

        cache_key = f"profile_{self.user_id}"
        cached_data = await self.get_cached_data(cache_key)
        if cached_data:
            return cached_data

        try:
            response = self.supabase.from_('user_profiles')\
                .select('*')\
                .eq('user_id', self.user_id)\
                .single()\
                .execute()
            
            if response.data:
                await self.set_cached_data(cache_key, response.data)
                return response.data
            return {}
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            return {}

    async def check_credits(self) -> bool:
        """Check if user has enough credits with caching"""
        if not self.requires_credits or not self.user_id:
            return True

        cache_key = f"credits_{self.user_id}"
        cached_result = await self.get_cached_data(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            response = self.supabase.rpc(
                'check_and_update_ai_credits',
                {'user_uuid': self.user_id}
            ).execute()
            
            await self.set_cached_data(cache_key, response.data, ttl=60)  # 1 minute TTL for credits
            return response.data
        except Exception as e:
            logger.error(f"Error checking credits: {e}")
            raise

    async def log_ai_request(self, service_name: str, status: str, metadata: dict = None):
        """Log AI request to Supabase with batch processing"""
        if not self.user_id:
            logger.warning("No user_id available for logging AI request")
            return

        try:
            # Using background task for logging
            asyncio.create_task(self._log_request(service_name, status, metadata))
        except Exception as e:
            logger.error(f"Error logging AI request: {e}")

    async def _log_request(self, service_name: str, status: str, metadata: dict = None):
        """Background task for logging requests"""
        try:
            self.supabase.from_('ai_requests_log').insert({
                'user_id': self.user_id,
                'service_name': service_name,
                'status': status,
                'metadata': metadata,
                'credits_used': self.requires_credits
            }).execute()
        except Exception as e:
            logger.error(f"Error in background logging: {e}")

    async def invalidate_cache(self, key: Optional[str] = None):
        """Invalidate specific cache entry or all user cache"""
        if key:
            cache_key = f"{self.cache_key}_{key}"
            self._cache.pop(cache_key, None)
        else:
            # Invalidate all cache entries for this user
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(self.cache_key)]
            for k in keys_to_remove:
                self._cache.pop(k, None)