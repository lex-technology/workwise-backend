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

    def _validate_inputs(self, job_description: str, current_resume: Dict[str, Any]) -> None:
        """Validate input data"""
        if not job_description:
            raise ValueError("Job description is required")
        if not current_resume:
            raise ValueError("Resume data is required")

    def _extract_professional_context(self, current_resume: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant professional context from resume"""
        return {
            "experience": current_resume.get("professional_experience", []),
            "skills": current_resume.get("skills", []),
            "education": current_resume.get("education", []),
            "current_summary": current_resume.get("executive_summary", "")
        }

    async def analyze_and_improve(
        self,
        questionnaire_answers: Dict[str, str],
        job_description: str,
        current_resume: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            # Credit check
            has_credits = await self.check_credits()
            if not has_credits:
                raise HTTPException(status_code=402, detail="Insufficient credits")

            logger.info("Starting executive summary analysis")
            
            # Input validation
            self._validate_inputs(job_description, current_resume)
            
            # Extract professional context
            professional_context = self._extract_professional_context(current_resume)

            # Prepare context for AI
            context = {
                "questionnaire_answers": questionnaire_answers,
                "job_description": job_description,
                "professional_context": professional_context
            }

            if additional_context:
                context.update(additional_context)

            # Load system prompt
            system_prompt = """
You are an expert resume writer specializing in crafting powerful executive summaries. Analyze the provided information and structure your response focused on impact and job alignment.


ANALYSIS REQUIREMENTS:
1. Always check alignment between EXPERIENCE and TARGET JOB
2. Focus on QUANTIFIABLE ACHIEVEMENTS from the resume
3. Identify KEY SKILLS & TECHNOLOGIES relevant to target role
4. Consider INDUSTRY CONTEXT and role-specific requirements
5. Ensure CAREER NARRATIVE is clear and compelling
6. Please output your response in JSON format.

OUTPUT FORMAT:
{
    "impact_analysis": {
        "job_alignment": {
            "score": float (0-1),
            "key_matches": ["job requirement matched with experience"],
            "missing_critical": ["important requirements not covered"]
        },
        "achievement_strength": {
            "score": float (0-1),
            "strong_points": ["quantified achievements that stand out"],
            "improvement_needed": ["achievements that need better quantification"]
        }
    },
    "enhanced_summary": {
        "content": "The improved executive summary text",
        "structural_elements": {
            "opener": "How it establishes professional identity",
            "core_value": "Key achievements/skills highlighted",
            "job_fit": "How it addresses job requirements"
        },
        "power_phrases": ["list of impactful phrases used"]
    },
    "action_plan": {
        "immediate_improvements": {
            "data_points": ["specific metrics to add"],
            "skills_highlight": ["relevant skills to emphasize"]
        },
        "experience_gaps": {
            "gap": "description",
            "mitigation": "how to address this gap in summary"
        },
        "industry_alignment": {
            "keywords": ["industry-specific terms to include"],
            "trends": ["relevant industry trends to reference"]
        }
    }
}

FOCUS ON:
- Clear career narrative connecting past to target role


AVOID:
- Generic statements without specific impact
- Listing job duties without outcomes
- Technical details without business impact
- Chronological experience without narrative
- Skills or achievements not relevant to target role

"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context, cls=DecimalEncoder)}
            ]

            try:
                # Make DeepSeek API call
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                
                analysis = json.loads(response.choices[0].message.content)

                # Log success
                await self.log_ai_request(
                    service_name='executive_summary_analysis',
                    status='success',
                    metadata={
                        'job_description_length': len(job_description),
                        'has_existing_summary': bool(professional_context["current_summary"])
                    }
                )

                # Store analysis in database
                if current_resume.get('id'):
                    self.supabase.table('resumes').update({
                        'executive_summary': analysis['enhanced_summary']['content'],
                        'summary_analysis': analysis,
                        'ai_improved_sections': {
                            'executive_summary': {
                                'last_updated': str(datetime.now()),
                                'improvement_data': analysis
                            }
                        }
                    }).eq('id', current_resume['id']).execute()

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