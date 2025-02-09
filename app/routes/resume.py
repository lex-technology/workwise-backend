from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import json
import logging
from pydantic import BaseModel
from typing import Optional, List
import traceback
from services.base_service import BaseService
from uuid import UUID
from fastapi import Depends
from .auth import get_user_id 

router = APIRouter()
logger = logging.getLogger(__name__)

class DateUpdate(BaseModel):
    date_applied: str

class ResumeService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        self.requires_credits = False
    
    async def get_resume(self, resume_id: int):
        try:
            resume_result = self.supabase.table('resumes').select('*').eq('id', resume_id).execute()
            
            if not resume_result.data:
                raise HTTPException(status_code=404, detail="Resume not found")
                
            resume = resume_result.data[0]
            experiences = await get_professional_experience(resume_id, self.supabase)
            
            response = {
                "id": resume_id,
                "contact_information": resume.get('contact_information', {}),
                "education": resume.get('education', []),
                "skills": resume.get('skills', []),
                "certificates": resume.get('certificates', []),
                "miscellaneous": resume.get('miscellaneous', []),
                "executive_summary": resume.get('executive_summary'),
                "professional_experience": experiences,
                "ai_improved_sections": resume.get('ai_improved_sections', {}),
                "job_description": resume.get('job_description'),
                "company_applied": resume.get('company_applied'),
                "role_applied": resume.get('role_applied'),
                "status": resume.get('status'),
                "personal_projects": resume.get('personal_projects', []),
                "summary_analysis": resume.get('summary_analysis'), 
            }

            # Only include jd_analysis if it exists and has content
            if resume.get('jd_analysis'):
                response["jd_analysis"] = resume['jd_analysis']
            print("Backend response data:", response)           
            return response
        
        except Exception as e:
            logger.error(f"Error fetching resume: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_all_applications(self, user_id: str | UUID):
        """
        Get all applications for a user
        Args:
            user_id (str | UUID): Supabase user UUID
        """
        try:
            # Get all applications ordered by date_applied, null dates will be last
            result = self.supabase.table('resumes').select(
                'id',
                'company_applied',
                'role_applied',
                'date_applied',
                'created_at',
                'status'
            ).eq('user_id', str(user_id)).order('date_applied', desc=True).execute()
            
            if not result.data:
                return {"applications": []}
                
            formatted_applications = [
                {
                    "id": app['id'],
                    "company": app['company_applied'],
                    "position": app['role_applied'],
                    "status": app['status'],
                    "date": app['date_applied'],
                    "created_at": app['created_at']
                }
                for app in result.data
            ]
                
            return {"applications": formatted_applications}
            
        except Exception as e:
            logger.error(f"Error fetching applications: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def update_section(self, resume_id: int, section: str, content: str):
        try:
            resume_result = self.supabase.table('resumes').select('ai_improved_sections').eq('id', resume_id).execute()
            
            if not resume_result.data:
                return JSONResponse(status_code=404, content={"detail": f"Resume with ID {resume_id} not found"})
                
            current_improved = resume_result.data[0].get('ai_improved_sections', {}) or {}
            current_improved[section] = True
            
            update_data = {
                section: content,
                'ai_improved_sections': current_improved
            }
            
            result = self.supabase.table('resumes').update(update_data).eq('id', resume_id).execute()
            
            return {
                "message": "Section updated successfully",
                "resume_id": resume_id,
                "improved_sections": current_improved
            }
            
        except Exception as e:
            logger.error(f"Error updating section: {str(e)}")
            return JSONResponse(status_code=500, content={"detail": f"Error updating section: {str(e)}"})

    async def update_experience_points(self, experience_id: int, modified_points: List[dict], deleted_points: List[int]):
        try:
            if deleted_points:
                self.supabase.table('experience_points').delete().in_('id', deleted_points).execute()

            for point in modified_points:
                update_data = {
                    'text': point.get('new_text'),
                    'relevance_score': point.get('relevance_score')
                }
                self.supabase.table('experience_points').update(update_data).eq('id', point.get('point_id')).execute()

            self.supabase.table('professional_experiences').update({'is_improved': True}).eq('id', experience_id).execute()

            return {
                "message": "Experience points updated successfully",
                "modified_count": len(modified_points),
                "deleted_count": len(deleted_points),
                "experience_improved": True
            }

        except Exception as e:
            logger.error(f"Error updating experience points: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating experience points: {str(e)}")

# Standalone function for other modules to import
async def get_professional_experience(resume_id: int, supabase_client = None):
    """
    Get professional experience for a resume. Can be used independently or within ResumeService.
    
    Args:
        resume_id (int): The ID of the resume
        supabase_client (Optional[Client]): Supabase client. If not provided, creates a new one.
    """
    try:
        # If no client provided, create a temporary service to get client
        if supabase_client is None:
            temp_service = BaseService()
            supabase_client = temp_service.supabase

        exp_result = supabase_client.table('professional_experiences').select('*').eq('resume_id', resume_id).execute()
        experiences = exp_result.data
        
        for exp in experiences:
            points_result = supabase_client.table('experience_points').select('*').eq('experience_id', exp['id']).execute()
            
            exp['points'] = [
                {
                    'id': point['id'],
                    'text': point['text'],
                    'relevance_score': point['relevance_score']
                }
                for point in points_result.data
            ]
            
            if exp.get('organization_description') is None:
                exp.pop('organization_description', None)
        
        return experiences
    except Exception as e:
        logger.error(f"Error fetching professional experience: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# FastAPI route handlers
@router.get("/get-resume/{resume_id}")
async def get_resume(
    resume_id: int, 
    user_id: str = Depends(get_user_id)  # Add authentication dependency
):
    try:
        service = ResumeService(user_id)
        
        # First check if the user has access to this resume
        resume_check = service.supabase.table('resumes')\
            .select('user_id')\
            .eq('id', resume_id)\
            .single()\
            .execute()
            
        if not resume_check.data:
            raise HTTPException(status_code=404, detail="Resume not found")
            
        if resume_check.data['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this resume")
        
        # If authorized, proceed with getting the resume data
        return await service.get_resume(resume_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_resume: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get-all-applications/{user_id}")
async def get_all_applications(user_id: UUID, request: Request):
    """
    Get all applications for a user.
    Requires authentication - user_id should be the Supabase UUID from the authenticated session.
    """
    service = ResumeService(str(user_id))  # Convert UUID to string for Supabase
    return await service.get_all_applications(str(user_id))

@router.post("/resume/update-section")
async def update_resume_section(request: Request):
    data = await request.json()
    service = ResumeService(request.state.user_id if hasattr(request.state, 'user_id') else None)
    return await service.update_section(
        resume_id=data.get('resumeId'),
        section=data.get('sectionTitle'),
        content=data.get('content')
    )

@router.post("/resume/update-experience-points")
async def update_experience_points(request: Request):
    data = await request.json()
    service = ResumeService(request.state.user_id if hasattr(request.state, 'user_id') else None)
    return await service.update_experience_points(
        experience_id=data.get('experienceId'),
        modified_points=data.get('modifiedPoints', []),
        deleted_points=data.get('deletedPoints', [])
    )

@router.put("/update-application-status/{resume_id}")
async def update_application_status(resume_id: int, status: str, request: Request):
    service = ResumeService(request.state.user_id if hasattr(request.state, 'user_id') else None)
    try:
        result = service.supabase.table('resumes').update(
            {'status': status}
        ).eq('id', resume_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Application not found")
            
        return {"message": "Status updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating application status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update-application-date/{resume_id}")
async def update_application_date(resume_id: int, date_update: DateUpdate, request: Request):
    service = ResumeService(request.state.user_id if hasattr(request.state, 'user_id') else None)
    try:
        # First get current status
        current = service.supabase.table('resumes').select('status').eq('id', resume_id).execute()
        
        if not current.data:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Determine new status
        current_status = current.data[0]['status']
        new_status = 'Applied' if current_status == 'Writing CV' else current_status
        
        # Update both date and status
        result = service.supabase.table('resumes').update({
            'date_applied': date_update.date_applied,
            'status': new_status
        }).eq('id', resume_id).execute()
        
        return {"message": "Application date updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating application date: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
# Add other resume-related endpoints
@router.get("/check-analysis/{resume_id}")
async def check_analysis(
    resume_id: int,
    user_id: str = Depends(get_user_id)
):
    try:
        logger.info(f"Checking analysis for resume {resume_id}")
        resume_service = ResumeService(user_id=user_id)
        resume_data = await resume_service.get_resume(resume_id)
        
        logger.info(f"Analysis status: {resume_data.get('analysis_status')}")
        logger.info(f"Has JD analysis: {bool(resume_data.get('jd_analysis'))}")
        
        response_data = {
            "status": "success",
            "analysis_status": resume_data.get('analysis_status'),
            "jd_analysis": resume_data.get('jd_analysis')
        }
        logger.info(f"Returning response: {response_data}")
        return response_data
    except Exception as e:
        logger.error(f"Error checking analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))