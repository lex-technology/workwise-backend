from typing import Dict, Any, Optional
import json
from .client import DeepSeekClientManager
import logging
from decimal import Decimal
from ..base_service import BaseService

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

class SkillsAnalysisService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        self.client = DeepSeekClientManager().get_client
        self.requires_credits = True 

    async def analyze_skills(
        self,
        resume_id: int,
        job_description: str,
        current_resume: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            # Check credits before proceeding
            if not await self.check_credits():
                raise Exception("Insufficient credits")
            
            if not job_description:
                raise ValueError("Job description is required")

            if not current_resume.get("skills"):
                logger.warning("No existing skills found")

            system_prompt = """You are an expert ATS and skills analyst. Analyze the alignment between current skills, 
            professional experience, and job description requirements. Provide the analysis in JSON format.

            IMPORTANT GUIDELINES:
            1. DO NOT ADD SKILLS THAT ARE ALREADY PRESENT IN THE RESUME
            2. Only add skills that are genuinely reflected in the professional experience 
            3. Categorize all skills as either technical_skills or soft_skills
            4. Provide SPECIFIC evidence from the professional experience for each suggested skill
            5. For missing skills, provide actionable development paths such as famous courses/certifications name, projects etc.
            6. Focus on skills that are most relevant to the job description
            7. TRY TO IDENTIFY AS MANY SKILLS AS POSSIBLE FOR ATS TO PICK UP
            8. Try to remove skills that are not relevant to the job description
            

            Return a JSON object with the following structure:
            {
                "added_skills": {
                    "technical_skills": [
                        {
                            "skill": "skill name",
                            "experience_reference": "specific experience that demonstrates this skill aligns with JD",
                        }
                    ],
                    "soft_skills": [
                        {
                            "skill": "skill name",
                            "experience_reference": "specific experience that demonstrates this skill aligns with JD",
                        }
                    ]
                },
                "removed_skills": {
                    "technical_skills": [
                        {
                            "skill": "skill name",
                            "reason": "specific reason for removal"
                        }
                    ],
                    "soft_skills": [
                        {
                            "skill": "skill name",
                            "reason": "specific reason for removal"
                        }
                    ]
                },
                "missing_skills": {
                    "technical_skills": [
                        {
                            "skill": "skill name",
                            "importance": "critical|recommended",
                            "jd_requirement": "JD requirement for this skill",
                            "development_path": "specific actionable steps"
                        }
                    ],
                    "soft_skills": [
                        {
                            "skill": "skill name",
                            "importance": "critical|recommended",
                            "jd_requirement": "JD requirement for this skill",
                            "development_path": "specific actionable steps"
                        }
                    ]
                }
            }"""

            # Convert the context to JSON with custom encoder
            context_json = json.dumps(current_resume, cls=DecimalEncoder)
            
            prompt = f"""
            Job Description: {job_description}
            
            Resume Context: {context_json}"""

            if additional_context:
                prompt += f"""
                Additional Context: {json.dumps(additional_context)}"""

            user_prompt = f"""Please analyze the following resume data and provide a JSON response according to the specified format.
            
            Resume Context: {prompt}"""

            response = self.client.chat.completions.create(
                # model="gpt-4-turbo-preview",
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" },
                temperature=0.7,
                max_tokens=6000
            )

            content = response.choices[0].message.content.strip()
            logger.info("Raw response from DeepSeek:")
            logger.info(f"Content type: {type(content)}")
            logger.info(f"Content: {content}")
            logger.debug(f"Raw OpenAI response: {content[:500]}...")

            try:
                analysis = json.loads(content)
                logger.info("Parsed analysis from DeepSeek:")
                logger.info(f"Analysis type: {type(analysis)}")
                logger.info(f"Analysis content: {analysis}")
                # Log successful request after the analysis is complete and parsed
                await self.log_ai_request(
                    service_name="skills_analysis",
                    status="success",
                    metadata={
                        "resume_id": resume_id,
                        "has_job_description": True,
                        "model": "deepseek-chat"
                    }
                )
                return analysis
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {str(e)}")
                logger.error(f"Failed JSON content: {content[:1000]}...")
                raise

        except Exception as e:
            logger.error(f"Error in analyze_skills: {str(e)}")
            raise 