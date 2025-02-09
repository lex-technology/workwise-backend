from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Dict, Optional
from services.deepseek.cover_letter_service import CoverLetterService
from .auth import get_user_id 
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class CoverLetterRequest(BaseModel):
    resume_id: int = Field(..., description="The ID of the resume")
    tone: str = Field(..., description="The tone of the cover letter")
    answers: Dict[str, str] = Field(default_factory=dict, description="Answers to cover letter questions")
    job_description: str = Field(..., description="The job description")

class EditCoverLetterRequest(BaseModel):
    edited_letter: str = Field(..., description="The edited cover letter content")

# async def get_user_id(request: Request) -> Optional[str]:
#     """Extract UUID from JWT token"""
#     auth_header = request.headers.get('Authorization')
#     if not auth_header or not auth_header.startswith('Bearer '):
#         raise HTTPException(status_code=401, detail="Authorization header missing")
        
#     token = auth_header.split(' ')[1]
#     try:
#         # Decode JWT without verification since Supabase already verified it
#         decoded = jwt.decode(token, options={"verify_signature": False})
#         return decoded.get('sub')  # 'sub' contains the user UUID in Supabase tokens
#     except Exception as e:
#         logger.error(f"Error decoding JWT: {e}")
#         raise HTTPException(status_code=401, detail="Invalid authentication token")

@router.post("/generate-cover-letter")
async def create_cover_letter(
    request: CoverLetterRequest,
    user_id: str = Depends(get_user_id)
):
    try:
        service = CoverLetterService(user_id)
        result = await service.generate_cover_letter(
            resume_id=request.resume_id,
            job_description=request.job_description,
            tone=request.tone,
            answers=request.answers
        )
        return result
    except Exception as e:
        logger.error(f"Error in create_cover_letter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get-cover-letter/{resume_id}")
async def get_cover_letter(
    resume_id: int,
    user_id: str = Depends(get_user_id)
):
    service = CoverLetterService(user_id)
    return await service.get_cover_letter(resume_id)

@router.put("/save-cover-letter/{resume_id}")
async def save_cover_letter(
    resume_id: int,
    request: EditCoverLetterRequest,
    user_id: str = Depends(get_user_id)
):
    service = CoverLetterService(user_id)
    return await service.save_cover_letter(resume_id, request.edited_letter)