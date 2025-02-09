from .client import DeepSeekClientManager
import logging
from ..base_service import BaseService
from typing import Dict, List, Any, Optional
import json
from decimal import Decimal
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class ExecutiveSummaryService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        self.client = DeepSeekClientManager().get_client
        self.requires_credits = True

    async def analyze_and_improve(
        self,
        questionnaire_answers: Dict[str, str],
        job_description: str,
        current_resume: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            # Verify user has enough credits using the existing function
            has_credits = await self.check_credits()
            if not has_credits:
                raise HTTPException(status_code=402, detail="Insufficient credits for executive summary analysis")

            logger.info("Starting executive summary analysis")
            
            # Validate inputs
            if not job_description:
                raise ValueError("Job description is required")
            
            if not current_resume.get("executive_summary"):
                logger.warning("No existing executive summary found")

            # System prompt remains the same
            system_prompt = """You are an expert resume writer specializing in executive summaries. Your goal is to transform the current executive summary into a powerful career snapshot that immediately demonstrates job fit.

WRITING GUIDELINES:
1. Length: Maximum 7 impactful lines
2. Structure: Use the STAR format to quantify achievements
3. Focus: Emphasize skills and experiences from the resume that directly match the job description. Feel free to remove unnecessary noise.
4. Authenticity: Only use experiences and skills explicitly stated in the resume
5. You can add to the executive summary but it has to be within the constraints of the actual professional experience.

OUTPUT JSON FORMAT:
{
    "enhanced_version": {
        "content": "improved executive summary text",
        "rationale": ["specific improvements made and their alignment with job requirements"]
    },
}

"""
    #  "additional_opportunities": {
    #     "relevant_experiences": {
    #         "experience1": "Found in your work history: Led a team of 5 in implementing CI/CD pipeline - relevant to the DevOps Engineer role requirement",
    #         "experience2": "Work achievement: Reduced cloud costs by 30% through optimization - aligns with the job's focus on cloud infrastructure",
    #         "experience3": ....
    #     }                   
    # }
            
            context = {
                "questionnaire_answers": questionnaire_answers,
                "job_description": job_description,
                "current_resume": {
                    "executive_summary": current_resume.get("executive_summary", ""),
                    "professional_experience": current_resume.get("professional_experience", []),
                    "education": current_resume.get("education", [])
                }
            }

            if additional_context:
                context.update(additional_context)

            context_json = json.dumps(context, cls=DecimalEncoder)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_json}
            ]

            try:
                # Make DeepSeek API call
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=8000
                )
                
                content = response.choices[0].message.content
                analysis = json.loads(content)

                # Log the AI request
                await self.log_ai_request(
                    service_name='executive_summary_analysis',
                    status='success',
                    metadata={
                        'job_description_length': len(job_description),
                        'has_existing_summary': bool(current_resume.get("executive_summary"))
                    }
                )

                # Store the analysis in Supabase
                if current_resume.get('id'):
                    self.supabase.table('resumes').update({
                        'executive_summary': analysis['enhanced_version']['content'],  # NEW
                        'summary_analysis': analysis
                    }).eq('id', current_resume['id']).eq('user_id', self.user_id).execute()

                return analysis
                
            except Exception as e:
                await self.log_ai_request(
                    service_name='executive_summary_analysis',
                    status='failed',
                    metadata={'error': str(e)}
                )
                logger.error(f"API Call Error: {str(e)}")
                raise

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in analyze_and_improve: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))