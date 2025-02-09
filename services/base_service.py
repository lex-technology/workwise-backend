# # base_service.py
# from supabase import create_client
# import logging
# from typing import Optional
# from dotenv import load_dotenv
# import os

# load_dotenv()

# logger = logging.getLogger(__name__)

# class BaseService:
#     def __init__(self, user_id: Optional[str] = None):
#         self.supabase = create_client(
#             supabase_url=os.getenv('SUPABASE_URL'),
#             supabase_key=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
#         )
#         self.user_id = user_id  # Direct assignment, no extraction needed
#         self.requires_credits = False

#     async def check_credits(self) -> bool:
#         """Check if user has enough credits"""
#         if not self.requires_credits or not self.user_id:
#             return True
            
#         try:
#             response = self.supabase.rpc(
#                 'check_and_update_ai_credits',
#                 {'user_uuid': self.user_id}
#             ).execute()

#             # newly added
#             # if response.data:
#             #     profile_response = self.supabase.from_('user_profiles').select('*').eq('user_id', self.user_id).single().execute()
#             #     if not profile_response.error:
#             #         # Emit an update event
#             #         self.supabase.channel('schema-db-changes').on(
#             #             'postgres_changes',
#             #             {
#             #                 'event': 'UPDATE',
#             #                 'schema': 'public',
#             #                 'table': 'user_profiles',
#             #                 'filter': f"user_id=eq.{self.user_id}"
#             #             }
#             #         ).subscribe()

#             return response.data
#         except Exception as e:
#             logger.error(f"Error checking credits: {e}")
#             raise

#     async def log_ai_request(self, service_name: str, status: str, metadata: dict = None):
#         """Log AI request to Supabase"""
#         try:
#             if not self.user_id:
#                 logger.warning("No user_id available for logging AI request")
#                 return

#             self.supabase.from_('ai_requests_log').insert({
#                 'user_id': self.user_id,
#                 'service_name': service_name,
#                 'status': status,
#                 'metadata': metadata,
#                 'credits_used': self.requires_credits
#             }).execute()
#         except Exception as e:
#             logger.error(f"Error logging AI request: {e}")

# base_service.py
from supabase import create_client
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

class BaseService:
    def __init__(self, user_id: Optional[str] = None):
        self.supabase = create_client(
            supabase_url=os.getenv('SUPABASE_URL'),
            supabase_key=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        )
        self.user_id = user_id
        self.requires_credits = False

    async def check_credits(self) -> bool:
        """Check if user has enough credits"""
        if not self.requires_credits or not self.user_id:
            return True
            
        try:
            response = self.supabase.rpc(
                'check_and_update_ai_credits',
                {'user_uuid': self.user_id}
            ).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error checking credits: {e}")
            raise

    async def update_resume_status(self, resume_id: int, status_type: str, status: str, metadata: Dict[str, Any] = None) -> None:
        """Update resume processing status"""
        try:
            logger.info(f"Updating {status_type} status to {status} for resume {resume_id}")
            update_data = {f'{status_type}_status': status}
            
            if metadata:
                logger.info("Fetching existing metadata...")
                try:
                    response = self.supabase.from_('resumes').select('metadata').execute()
                    logger.info(f"Metadata fetch response: {response}")
                    
                    if response.data and len(response.data) > 0:
                        existing_metadata = response.data[0].get('metadata', {}) or {}
                        update_data['metadata'] = {**existing_metadata, **metadata}
                        logger.info(f"Combined metadata: {update_data['metadata']}")
                    else:
                        logger.info("No existing metadata found, using new metadata only")
                        update_data['metadata'] = metadata
                except Exception as e:
                    logger.error(f"Error fetching metadata: {e}")
                    logger.info("Using new metadata only due to fetch error")
                    update_data['metadata'] = metadata

            logger.info(f"Sending update with data: {update_data}")
            response = self.supabase.from_('resumes').update(update_data).eq('id', resume_id).execute()
            logger.info(f"Update response: {response}")
            
        except Exception as e:
            logger.error(f"Error updating resume status: {e}")
            logger.error("Full traceback:", exc_info=True)
            raise

    async def log_ai_request(self, service_name: str, status: str, metadata: dict = None):
        """Log AI request to Supabase"""
        try:
            if not self.user_id:
                logger.warning("No user_id available for logging AI request")
                return

            self.supabase.from_('ai_requests_log').insert({
                'user_id': self.user_id,
                'service_name': service_name,
                'status': status,
                'metadata': metadata,
                'credits_used': self.requires_credits
            }).execute()
        except Exception as e:
            logger.error(f"Error logging AI request: {e}")
            raise