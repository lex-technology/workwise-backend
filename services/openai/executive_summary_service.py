from .client import OpenAIClientManager
import logging
from typing import Dict, List, Any, Optional
import json
from decimal import Decimal

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class ExecutiveSummaryService:
    def __init__(self):
        self.client = OpenAIClientManager().get_client

    async def analyze_and_improve(
        self,
        questionnaire_answers: Dict[str, str],
        job_description: str,
        current_resume: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            logger.info("Starting executive summary analysis")
            
            # Validate inputs
            if not job_description:
                raise ValueError("Job description is required")
            
            if not current_resume.get("executive_summary"):
                logger.warning("No existing executive summary found")

            # Prepare the system prompt
            system_prompt = """You are an expert resume writer specializing in executive summaries. 
            Analyze the current executive summary and create improved versions that are:
            1. Maximum 5 lines
            2. Focused on job fit rather than general background (IMPORTANT)
            3. Achievement-oriented and impactful
            4. USE THE STAR FORMAT when writing any experiences
            5. Punchy and aligned with the job description
            6. DO NOT MAKE UP EXPPERIENCES AND SKILLs not explicitly stated in the resume
            7. Directly address the job description and the skills and experiences that are most relevant to the job
            8. example of suggestions: {Emphasize on the use of ERD : e.g. successfully used ERD to design a database for a new system that increased efficiency by 20%}

            OUTPUT JSON FORMAT:
            {
                "current_analysis": {
                    "score": float (0-1),
                    "reasoning": "detailed explanation",
                    "areas_of_improvement": ["area1", "area2"]
                },
                "version": 
                    {
                        "content": "executive summary text",
                        "tone": "tone description",
                        "explanation": {
                            "improvements_made": ["improvement1", "improvement2"],
                            "alignment_with_jd": "explanation of job fit",
                            "key_selling_points": ["point1", "point2"]
                        },
                        "score": float (0-1)
                    },
                "suggestions": {
                         "missing_elements": {
                                suggestion1: "example of how to write the missing element", # (see point 8 in the system prompt)
                                suggestion2: "example of how to write the missing element"
                        },
                         "enhancement_opportunities": {
                                "opportunity1": "example of how to write the enhancement opportunity", #similar to suggestion 1
                                "opportunity2": "example of how to write the enhancement opportunity"
                        }
                    }
            }"""
            # If want to change to multiple versions, change the context to a list of dictionaries
            # Prepare the context for AI
            
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

            # Use DecimalEncoder when dumping context to JSON
            context_json = json.dumps(context, cls=DecimalEncoder)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_json}
            ]

            try:
                response = self.client.chat.completions.create(

                    # model="gpt-4-1106-preview",  # Using the latest model for better analysis
                    model="gpt-4o-mini",
                    messages=messages,
                    response_format={ "type": "json_object" },
                    temperature=0.7
                )
                
                content = response.choices[0].message.content.strip()
                
                # Log the raw response for debugging
                logger.debug(f"Raw OpenAI response: {content[:500]}...")
                
                try:
                    analysis = json.loads(content)
                    return analysis
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON Parse Error: {str(e)}")
                    logger.error(f"Failed JSON content: {content[:1000]}...")
                    raise
                    
            except Exception as e:
                logger.error(f"API Call Error: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Error in analyze_and_improve: {str(e)}")
            raise

    def _validate_executive_summary(self, summary: str) -> bool:
        """
        Validates if the executive summary meets our requirements
        - Max 5 lines
        - Contains achievements/metrics
        - Job-focused
        """
        if not summary:
            return False
            
        lines = summary.split('\n')
        if len(lines) > 5:
            return False
            
        # Add more validation as needed
        return True 
    

    # class AIAnalysisInput:
    # # Core inputs
    # questionnaire_answers: Dict[str, str]  # Flexible dictionary for questionnaire
    # job_description: str
    # current_resume: {
    #     executive_summary: str,
    #     professional_experience: List[Experience],
    #     education: List[Education]
    # }
    
    # # Extensible for future inputs
    # additional_context: Dict[str, Any]  # For future extensions like skills, certifications, etc.