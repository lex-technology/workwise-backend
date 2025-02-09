# application_process.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Header
from services.deepseek.parser_service import ResumeParserService
from services.deepseek.jd_analysis_service import JDAnalysisService
import logging
from services.base_service import BaseService
import json
from typing import Dict, Any, Optional
from datetime import datetime
from .auth import get_user_id
from fastapi import BackgroundTasks
import hashlib
from .resume import ResumeService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/parse-resume")
async def parse_resume(
    resume: Optional[UploadFile] = None,
    parsed_resume_id: Optional[int] = Form(None),
    companyApplied: str = Form(...),
    roleApplied: str = Form(...),
    jobDescription: str = Form(...),
    user_id: str = Depends(get_user_id),
    authorization: Optional[str] = Header(None)
):
    print("\n=== Starting New Resume Parse Request ===")
    print(f"User ID: {user_id}")
    print(f"Using existing resume: {parsed_resume_id is not None}")

    try:
        print("\n1. Initializing services...")
        parser_service = ResumeParserService(user_id=user_id)
        base_service = BaseService(user_id=user_id)

        # Get or create parsed resume data
        parsed_data = None
        if parsed_resume_id:
            print("\n2a. Getting existing parsed resume...")
            parsed_response = base_service.supabase.from_('parsed_resumes').select('*').eq('id', parsed_resume_id).single().execute()
            if not parsed_response.data:
                raise HTTPException(status_code=404, detail="Parsed resume not found")
            parsed_data = parsed_response.data['parsed_data']
            print("Retrieved existing parsed data")
        else:
            print("\n2b. Processing new resume...")
            if not resume:
                raise HTTPException(status_code=400, detail="Either resume file or parsed_resume_id must be provided")
            
            content = await resume.read()
            print(f"File size: {len(content)} bytes")
            
            # Generate hash and check for existing parse
            file_hash = hashlib.md5(content).hexdigest()
            existing_parse = base_service.supabase.from_('parsed_resumes').select('*').eq('file_hash', file_hash).execute()
            
            if existing_parse.data:
                print("Found existing parse for this resume")
                parsed_data = existing_parse.data[0]['parsed_data']
            else:
                print("Parsing new resume...")
                result = await parser_service.parse_resume(content, resume.filename)
                parsed_data = result['parsed_data']
                metadata = result.get('metadata', {})

                # Store parsed result with filename
                parse_store_data = {
                    'user_id': user_id,
                    'file_hash': file_hash,
                    'parsed_data': parsed_data,
                    'original_filename': metadata.get('original_filename', resume.filename),
                }
                base_service.supabase.from_('parsed_resumes').insert(parse_store_data).execute()
                print("Stored new parsed data")

        print("\n3. Creating resume entry...")
        initial_resume_data = {
            'user_id': user_id,
            'job_description': jobDescription,
            'company_applied': companyApplied,
            'role_applied': roleApplied,
            'status': 'Writing CV',
            'parsing_status': 'completed',  # Since we already have parsed data
            'analysis_status': 'pending'
        }

        try:
            resume_response = base_service.supabase.from_('resumes').insert(initial_resume_data).execute()
            resume_id = resume_response.data[0]['id']
            print(f"Created resume entry with ID: {resume_id}")
        except Exception as db_error:
            print(f"Database Error: {str(db_error)}")
            raise

        print("\n4. Processing parsed data...")
        sections = parsed_data.get('content', {}).get('sections', [])
        
        print("\n5. Updating resume with parsed data...")
        update_data = {
            'contact_information': next((s.get('content', {}) for s in sections if s.get('type') == 'contact_information'), {}),
            'education': next((s.get('entries', []) for s in sections if s.get('type') == 'education'), []),
            'skills': next((s.get('entries', []) for s in sections if s.get('type') == 'skills'), []),
            'certificates': next((s.get('entries', []) for s in sections if s.get('type') == 'certificates'), []),
            'miscellaneous': next((s.get('entries', []) for s in sections if s.get('type') == 'miscellaneous'), []),
            'executive_summary': next((s.get('content', '') for s in sections if s.get('type') == 'executive summary'), ''),
            'personal_projects': next((s.get('entries', []) for s in sections if s.get('type') == 'personal_projects'), [])
        }
        
        base_service.supabase.from_('resumes').update(update_data).eq('id', resume_id).execute()

        print("\n6. Processing professional experience...")
        prof_exp = next((s.get('entries', []) for s in sections if s.get('type') == 'professional_experience'), [])
        print(f"Found {len(prof_exp)} experiences")
        
        for i, exp in enumerate(prof_exp, 1):
            print(f"\nProcessing experience {i}/{len(prof_exp)}...")
            exp_data = {
                'resume_id': resume_id,
                'organization': exp.get('organization', ''),
                'role': exp.get('role', ''),
                'duration': exp.get('duration', ''),
                'location': exp.get('location', ''),
                'organization_description': exp.get('organization_description', '')
            }
            
            exp_response = base_service.supabase.from_('professional_experiences').insert(exp_data).execute()
            exp_id = exp_response.data[0]['id']

            if 'points' in exp and exp['points']:
                points_data = [{'experience_id': exp_id, 'text': point} for point in exp['points']]
                base_service.supabase.from_('experience_points').insert(points_data).execute()

        # Trigger JD analysis in background
        # Note: Frontend will handle showing the resume while this completes
        # background_tasks = BackgroundTasks()
        # background_tasks.add_task(analyze_jd, resume_id, user_id, authorization)

        return {
            "status": "success",
            "resume_id": resume_id,
            "message": "Resume processed successfully",
            "is_reused": parsed_resume_id is not None or existing_parse.data is not None
        }

    except Exception as e:
        print("\n!!! General Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/analyze-jd/{resume_id}")
async def analyze_jd(
    resume_id: int,
    user_id: str = Depends(get_user_id),
    authorization: Optional[str] = Header(None)
):
    try:
        logger.info(f"Starting JD analysis for resume {resume_id}, user {user_id}")
        jd_analysis_service = JDAnalysisService(user_id=user_id)
        base_service = BaseService(user_id=user_id)

        # Get resume data using the service
        resume_service = ResumeService(user_id=user_id)
        resume_data = await resume_service.get_resume(resume_id)
        
        if not resume_data:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Update status to in progress
        logger.info("Updating analysis status to in_progress")
        await base_service.update_resume_status(resume_id, 'analysis', 'in_progress')

        # Perform analysis
        logger.info("Starting JD analysis...")
        analysis = await jd_analysis_service.analyze(
            job_description=resume_data['job_description'],
            resume_data=resume_data
        )
        logger.info("JD analysis completed successfully")

        # Update resume with analysis
        logger.info("Updating resume with analysis results")
        update_data = {
            'analysis_status': 'completed',
            'jd_analysis': analysis
        }
        update_response = base_service.supabase.from_('resumes').update(update_data).eq('id', resume_id).execute()
        logger.info(f"Update response: {update_response}")

        return {
            "status": "success",
            "resume_id": resume_id,
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"Error in JD analysis: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        if 'resume_id' in locals():
            await base_service.update_resume_status(resume_id, 'analysis', 'failed', {'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@router.get("/parsed-resumes")
async def get_parsed_resumes(
    user_id: str = Depends(get_user_id),
    authorization: Optional[str] = Header(None)
):
    print("\n=== Fetching Parsed Resumes ===")
    print(f"User ID: {user_id}")

    try:
        base_service = BaseService(user_id=user_id)
        
        print("Querying parsed_resumes table...")
        response = base_service.supabase.from_('parsed_resumes')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .execute()
        
        print(f"Query response data: {response.data}")
        
        parsed_resumes = response.data if response.data else []
        print(f"Found {len(parsed_resumes)} parsed resumes")

        # For each parsed resume, get the most recent application
        for resume in parsed_resumes:
            try:
                print(f"\nFetching recent application for parsed resume {resume['id']}")
                recent_app = base_service.supabase.from_('resumes')\
                    .select('company_applied,role_applied,created_at')\
                    .eq('parsed_resume_id', resume['id'])\
                    .order('created_at', desc=True)\
                    .limit(1)\
                    .execute()
                
                if recent_app.data and len(recent_app.data) > 0:
                    resume['last_used'] = {
                        'company': recent_app.data[0]['company_applied'],
                        'role': recent_app.data[0]['role_applied'],
                        'date': recent_app.data[0]['created_at']
                    }
                    print(f"Added last used info for resume {resume['id']}")
            except Exception as e:
                print(f"Error fetching recent application: {str(e)}")
                continue

        # Clean up the response
        for resume in parsed_resumes:
            # Add original filename if available
            if 'original_filename' not in resume:
                resume['original_filename'] = 'Unnamed Resume'
                
            # Add formatted date
            resume['formatted_date'] = resume['created_at']

        print("\nReturning parsed resumes data")
        print(f"Number of resumes: {len(parsed_resumes)}")
        return parsed_resumes

    except Exception as e:
        print("\n!!! Error fetching parsed resumes !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("Full traceback:")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
