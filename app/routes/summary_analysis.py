from fastapi import APIRouter, Request, HTTPException, Depends 
from services.deepseek.executive_summary_service import ExecutiveSummaryService
import logging
import json
from decimal import Decimal
from .auth import get_user_id

router = APIRouter()
logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

@router.get("/resume/{resume_id}/summary-analysis")
async def get_summary_analysis(
    resume_id: int,
    user_id: str = Depends(get_user_id)
):
    try:
        # Initialize service with user_id
        executive_summary_service = ExecutiveSummaryService(user_id)
        
        try:
            # Check resume ownership
            resume_result = executive_summary_service.supabase\
                .from_('resumes')\
                .select('user_id')\
                .eq('id', resume_id)\
                .single()\
                .execute()

            if not resume_result.data:
                raise HTTPException(status_code=404, detail="Resume not found")
                
            if resume_result.data.get('user_id') != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to access this resume")

            # Get summary analysis
            analysis_result = executive_summary_service.supabase\
                .from_('resumes')\
                .select('summary_analysis')\
                .eq('id', resume_id)\
                .single()\
                .execute()
            
            if not analysis_result.data:
                return {"analysis": None}
                
            return {"analysis": analysis_result.data.get('summary_analysis')}
            
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching summary analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume/analyze-executive-summary")
async def analyze_executive_summary(
    request: Request,
    user_id: str = Depends(get_user_id)
):
    try:
        data = await request.json()
        resume_id = data.get('resumeId')
        if not resume_id:
            raise HTTPException(status_code=400, detail="Resume ID is required")

        # Initialize service with user_id
        executive_summary_service = ExecutiveSummaryService(user_id)
        
        try:
            # Check resume ownership
            resume_result = executive_summary_service.supabase\
                .from_('resumes')\
                .select('''
                    id,
                    job_description,
                    executive_summary,
                    education (
                        institution,
                        degree,
                        duration,
                        grade,
                        relevant_courses
                    )
                ''')\
                .eq('id', resume_id)\
                .single()\
                .execute()
            
            if not resume_result.data:
                raise HTTPException(status_code=404, detail="Resume not found")
            
            if resume_result.data.get('user_id') != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to access this resume")
            
            resume_data = resume_result.data

            # Fetch professional experiences with points
            experiences_result = executive_summary_service.supabase\
                .from_('professional_experiences')\
                .select('''
                    id,
                    organization,
                    role,
                    duration,
                    location,
                    is_improved,
                    organization_description,
                    experience_analysis,
                    experience_points (
                        text,
                        relevance_score
                    )
                ''')\
                .eq('resume_id', resume_id)\
                .execute()

            professional_experiences = []
            if experiences_result.data:
                for exp in experiences_result.data:
                    experience = {
                        'organization': exp['organization'],
                        'role': exp['role'],
                        'duration': exp['duration'],
                        'location': exp['location'],
                        'organization_description': exp['organization_description'],
                        'points': [point['text'] for point in exp.get('experience_points', [])]
                    }
                    professional_experiences.append(experience)

            current_resume = {
                "id": resume_id,
                "executive_summary": resume_data['executive_summary'],
                "professional_experience": professional_experiences,
                "education": resume_data['education']
            }

            # Get analysis results from service
            analysis_result = await executive_summary_service.analyze_and_improve(
                questionnaire_answers=data.get('answers', {}),
                job_description=resume_data['job_description'],
                current_resume=current_resume,
                additional_context=data.get('additional_context')
            )
            
            # Convert Decimal values for JSON serialization
            analysis_json = json.dumps(analysis_result, cls=DecimalEncoder)
            parsed_analysis = json.loads(analysis_json)

            # Store analysis results
            update_result = executive_summary_service.supabase\
                .from_('resumes')\
                .update({
                    'summary_analysis': parsed_analysis,
                    'ai_improved_sections': {
                        'executive_summary': True,
                        **(resume_data.get('ai_improved_sections') or {})
                    }
                })\
                .eq('id', resume_id)\
                .eq('user_id', user_id)\
                .execute()

            return {"analysis": parsed_analysis}

        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing executive summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))