from .client import DeepSeekClientManager
import logging
import json
from typing import Dict, Any
from services.base_service import BaseService

logger = logging.getLogger(__name__)

class ExperienceAnalyzerService(BaseService):
    def __init__(self, user_id: str):
        super().__init__(user_id)
        self.requires_credits = True  # This service requires credits
        self.client = DeepSeekClientManager().get_client

    async def analyze_experience(self, experience: Dict[str, Any], job_description: str) -> Dict[str, Any]:
        try:
            has_credits = await self.check_credits()
            if not has_credits:
                raise ValueError("Insufficient credits for analysis")
            logger.info("Starting experience analysis process")
            
            # Validate input
            if not experience or 'points' not in experience:
                logger.error("Analysis Error: Invalid experience format")
                raise ValueError("Invalid experience format")

            system_prompt = """You are an expert resume analyst. Analyze each experience point against the provided job description.

OUTPUT JSON FORMAT:
{
    "experience_analysis": {
        "points_analysis": [
            {
                "original_text": "original point text",

                "impact_score": 0.0-1.0,
                "relevance": {
                    "score": 0.0-1.0,
                    "reason": "detailed explanation of relevance to job description",
                    "matching_requirements": ["specific JD requirements this point addresses"],
                    "suggested_angle_shifts": ["how can we change the point to better match the JD"]
                },
                "scoring_breakdown": {
                    "star_format": {
                        "score": 0.0-1.0,
                        "feedback": "how well it follows STAR format"
                    },
                    "conciseness": {
                        "score": 0.0-1.0,
                        "feedback": "evaluation of conciseness"
                    },
                    "ats_optimization": {
                        "score": 0.0-1.0,
                        "feedback": "ATS-related feedback",
                        "suggested_keywords": ["from JD"]
                    }
                },
                "improvement": {
                    "rewritten_point": "AI suggested rewrite",
                    "explanation": "why the rewrite is better",
                    "improvements_made": [
                        "specific improvements listed"
                    ]
                },
                "repetition": {
                    "is_repeated": false,
                    "similar_points": [],
                    "similarity_explanation": "if repeated, explain where and how"
                }
            }
        ],
    }
}

ANALYSIS GUIDELINES:
1. For each experience point:
   - Calculate relevance score against specific JD requirements
   - Calculate impact_score as average of all scoring components
   - Evaluate STAR format implementation
   - Check conciseness and clarity
   - Assess grammar and professional tone
   - Analyze ATS optimization using JD keywords
   - Identify any repetition with other points
2. Provide specific, actionable improvement suggestions that follows the STAR format with quantifiable results such as "improved X by Y%" or just "improved X". Do use placeholders to indicate unsure percentages.
3. Focus on industry-standard terminology from JD
4. Ensure each point's relevance is evaluated independently
5. Suggest ways to incorporate missing JD requirements
6. Make sure there is at least one point that is not relevant to the JD, not impactful to the JD and low on impact score both below 0.3

"""

            try:
                response = self.client.chat.completions.create(
                    # model="gpt-4-turbo-preview",
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps({
                            "experience": experience,
                            "job_description": job_description
                        })}
                    ],
                    response_format={ "type": "json_object" },
                    temperature=0.7,
                    max_tokens=6000
                )
                
                content = response.choices[0].message.content.strip()
                logger.debug(f"Raw OpenAI response: {content[:500]}...")
                
                try:
                    analysis = json.loads(content)
                    if not isinstance(analysis, dict) or 'experience_analysis' not in analysis:
                        logger.error("Invalid analysis structure")
                        raise ValueError("Invalid analysis structure")
                    
                                # Log successful request
                    await self.log_ai_request(
                        service_name="experience_analysis",
                        status="success",
                        metadata={
                            "experience_id": experience.get("id"),
                            "points_analyzed": len(experience.get("points", []))
                        }
                    )

                    return analysis
                
                except Exception as e:
                    # Log failed request
                    await self.log_ai_request(
                        service_name="experience_analysis",
                        status="error",
                        metadata={
                            "experience_id": experience.get("id"),
                            "error": str(e)
                        }
                    )
                    logger.error(f"Error in analyze_experience: {str(e)}")
                    raise
                 
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON Parse Error: {str(e)}")
                    logger.error(f"Failed JSON content: {content[:1000]}...")
                    raise
                    
            except Exception as e:
                logger.error(f"API Call Error: {str(e)}")
                raise

            
            
        except Exception as e:
            logger.error(f"Error in analyze_experience: {str(e)}")
            raise
