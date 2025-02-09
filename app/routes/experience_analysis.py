# experience_analysis.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from services.deepseek.analyzer_service import ExperienceAnalyzerService
from .auth import get_user_id
from services.base_service import BaseService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/analyze-experience")
async def analyze_experience(
    request: Dict[str, Any],
    user_id: str = Depends(get_user_id)  # Get user_id from JWT token
):
    try:
        logger.info(f"Analyzing experience with data: {request}")
        
        resume_id = request.get('resumeId')
        experience = request.get('experience')
        
        if not experience:
            raise HTTPException(status_code=400, detail="No experience data provided")
            
        try:
            # Initialize analyzer service with user_id
            analyzer = ExperienceAnalyzerService(user_id)
            
            # Get job description from Supabase
            resume_data = analyzer.supabase.from_('resumes')\
                .select('job_description')\
                .eq('id', resume_id)\
                .single()\
                .execute()
                
            if not resume_data.data:
                raise HTTPException(status_code=404, detail="Resume not found")
                
            job_description = resume_data.data.get('job_description')
            
            if not job_description:
                raise HTTPException(
                    status_code=400, 
                    detail="Job description is required for experience analysis"
                )

            # Create points mapping
            existing_points = {
                point['text']: point['id'] 
                for point in experience.get('points', [])
            }
            
            # Run analysis
            analysis_result = await analyzer.analyze_experience(experience, job_description)
            
            # Add point_ids to analysis and store new points
            for point in analysis_result['experience_analysis']['points_analysis']:
                point_text = point['original_text']
                if point_text in existing_points:
                    point['point_id'] = existing_points[point_text]
                else:
                    # Insert new point using Supabase
                    new_point = analyzer.supabase.from_('experience_points')\
                        .insert({
                            'experience_id': experience['id'],
                            'text': point_text
                        })\
                        .execute()
                    point['point_id'] = new_point.data[0]['id']
            
            # Store analysis in professional_experience table
            analyzer.supabase.from_('professional_experiences')\
                .update({
                    'experience_analysis': analysis_result
                })\
                .eq('id', experience['id'])\
                .execute()
            
            return analysis_result
            
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        logger.error(f"Error in analyze_experience: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/experience/{experience_id}/analysis")
async def get_experience_analysis(
    experience_id: int,
    user_id: str = Depends(get_user_id)
):
    try:
        logger.info(f"Getting analysis for experience_id: {experience_id}, user_id: {user_id}")
        base_service = BaseService(user_id)
        
        try:
            logger.info("Attempting to query professional_experiences table")  # Updated table name in log
            
            # Get analysis from Supabase
            query = base_service.supabase.from_('professional_experiences')\
                .select('experience_analysis')\
                .eq('id', experience_id)
            
            result = query.single().execute()
            logger.info(f"Query result: {result}")
            
            if not result.data or not result.data.get('experience_analysis'):
                logger.info("No analysis found")
                return {"analysis": None}
                
            logger.info("Successfully retrieved analysis")
            return {"analysis": result.data['experience_analysis']}
            
        except Exception as e:
            logger.info(f"No analysis found or error: {str(e)}")
            return {"analysis": None}
            
    except Exception as e:
        logger.error(f"Error fetching experience analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))