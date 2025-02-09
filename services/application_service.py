# services/application_service.py
from typing import Optional
from .base_service import BaseService
import logging

logger = logging.getLogger(__name__)

class ApplicationService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        
    async def check_application_limit(self) -> bool:
        """Check if user can create more applications"""
        try:
            # First check if user is paid
            result = await self.supabase.table('user_profiles') \
                .select('is_paid_user') \
                .eq('user_id', self.user_id) \
                .single() \
                .execute()
                
            if result.data and result.data.get('is_paid_user'):
                return True
                
            # If not paid, check application count
            result = await self.supabase.table('resumes') \
                .select('id', count='exact') \
                .eq('user_id', self.user_id) \
                .execute()
                
            return (result.count or 0) < 5
            
        except Exception as e:
            logger.error(f"Error checking application limit: {e}")
            raise
            
    async def create_application(self, data: dict):
        """Create new application with limit check"""
        can_create = await self.check_application_limit()
        if not can_create:
            raise Exception("Free user application limit reached")
            
        return await self.supabase.table('resumes') \
            .insert(data) \
            .execute()
            
    async def get_applications(self):
        """Get applications with proper limit handling"""
        try:
            result = await self.supabase.table('user_profiles') \
                .select('is_paid_user') \
                .eq('user_id', self.user_id) \
                .single() \
                .execute()
                
            is_paid = result.data and result.data.get('is_paid_user')
            
            query = self.supabase.table('resumes') \
                .select('*') \
                .eq('user_id', self.user_id) \
                .order('created_at', desc=True)
                
            if not is_paid:
                query = query.limit(5)
                
            return await query.execute()
            
        except Exception as e:
            logger.error(f"Error fetching applications: {e}")
            raise