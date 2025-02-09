# app/routes/skills_analysis.py
from fastapi import APIRouter, Request, HTTPException, Depends
from services.deepseek.skills_service import SkillsAnalysisService
from app.routes.auth import get_user_id
import logging
import json
from decimal import Decimal

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/resume/analyze-skills")
async def analyze_skills(request: Request, user_id: str = Depends(get_user_id)):
    try:
        data = await request.json()
        resume_id = data.get('resumeId')
        
        if not resume_id:
            raise HTTPException(status_code=400, detail="Resume ID is required")

        skills_service = SkillsAnalysisService(user_id=user_id)
        
        # Fetch resume data
        resume_data = skills_service.supabase.from_('resumes')\
            .select('job_description, skills, education')\
            .eq('id', resume_id)\
            .single()\
            .execute()

        if not resume_data.data:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Get professional experience data
        experience_points = skills_service.supabase.from_('experience_points')\
            .select('experience_id, text, relevance_score')\
            .eq('experience_id', resume_id)\
            .execute()

        experiences = skills_service.supabase.from_('professional_experiences')\
            .select('*')\
            .eq('resume_id', resume_id)\
            .execute()

        professional_experience = []
        if experiences.data:
            for exp in experiences.data:
                exp_points = [p for p in experience_points.data if p['experience_id'] == exp['id']]
                exp['points'] = exp_points
                professional_experience.append(exp)

        current_resume = {
            "skills": resume_data.data.get('skills', {}),
            "professional_experience": professional_experience,
            "education": resume_data.data.get('education', [])
        }

        if not resume_data.data.get('job_description'):
            raise HTTPException(
                status_code=400, 
                detail="Job description is required to analyze skills"
            )

        # Get analysis result
        analysis_result = await skills_service.analyze_skills(
            resume_id=resume_id,
            job_description=resume_data.data['job_description'],
            current_resume=current_resume,
            additional_context=data.get('additional_context')
        )

        # Store raw analysis result in JSONB column
        update_result = skills_service.supabase.from_('resumes')\
            .update({
                'skills_analysis': analysis_result  # Supabase will handle JSONB conversion
            })\
            .eq('id', resume_id)\
            .execute()

        return {"analysis": analysis_result}

    except Exception as e:
        logger.error(f"Error analyzing skills", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resume/{resume_id}/skills-analysis")
async def get_skills_analysis(resume_id: int, user_id: str = Depends(get_user_id)):
    try:
        skills_service = SkillsAnalysisService(user_id=user_id)
        
        result = skills_service.supabase.from_('resumes')\
            .select('skills_analysis')\
            .eq('id', resume_id)\
            .single()\
            .execute()

        if not result.data or not result.data.get('skills_analysis'):
            return {"analysis": None}

        # Return raw analysis data
        return {"analysis": result.data['skills_analysis']}

    except Exception as e:
        logger.error(f"Error fetching skills analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))