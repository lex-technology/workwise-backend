# jd_analysis_service.py
from typing import Dict, List, Any
from .client import DeepSeekClientManager
import logging
from ..base_service import BaseService
import json
from typing import Optional

logger = logging.getLogger(__name__)

class JDAnalysisService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        self.client = DeepSeekClientManager().get_client

    def _format_resume_sections(self, resume_data: Dict[str, Any]) -> Dict[str, str]:
        """Format all resume sections for prompt"""
        try:
            # Format skills
            skills = resume_data.get('skills', [])
            technical_skills = [skill.get('technical_skills', '') for skill in skills if skill.get('technical_skills')]
            soft_skills = [skill.get('soft_skills', '') for skill in skills if skill.get('soft_skills')]
            
            skills_text = "Technical Skills: " + ", ".join(filter(None, technical_skills)) + "\n"
            skills_text += "Soft Skills: " + ", ".join(filter(None, soft_skills))

            # Format experience
            experience = resume_data.get('professional_experience', [])
            logger.info(f"Processing {len(experience)} experiences")
            
            experience_text = []
            for exp in experience:
                exp_text = f"- {exp['organization']}: {exp['role']} ({exp['duration']})"
                points = [point['text'] for point in exp.get('points', [])]
                if points:
                    exp_text += "\n  " + "\n  ".join(points)
                experience_text.append(exp_text)
            
            experience_text = "\n".join(experience_text)

            # Format education
            education = resume_data.get('education', [])
            logger.info(f"Processing {len(education)} education entries")
            
            education_text = "\n".join([
                f"- {edu['institution']}: {edu['degree']} ({edu['duration']})"
                for edu in education
            ])

            # Format projects
            projects = resume_data.get('personal_projects', [])
            logger.info(f"Processing {len(projects)} projects")
            
            project_text = []
            for proj in projects:
                proj_text = f"- {proj['project_name']}"
                if proj.get('project_experience'):
                    proj_text += "\n  " + "\n  ".join(proj['project_experience'])
                project_text.append(proj_text)
            
            project_text = "\n".join(project_text)

            return {
                "skills": skills_text,
                "experience": experience_text,
                "education": education_text,
                "projects": project_text
            }

        except Exception as e:
            logger.error(f"Error formatting resume sections: {e}")
            raise

    def _create_analysis_prompt(self, job_description: str, formatted_sections: Dict[str, str]) -> str:
        """Create the analysis prompt with formatted sections"""
        return f"""You are a professional resume analyst and career coach. Your response must be VALID JSON and match this exact structure:
{{
    "jd_analysis": [
        {{
            "line_text": "Original line from JD",
            "skill_type": "technical skills/domain knowledge/soft skills",
            "identified_skills": "skill name",
            "has_skill": true/false,
            "source": {{
                "evidence": "specific evidence from resume if has_skill is true",
                "reason": "explanation of how the evidence demonstrates the skill"
            }},
            "gap_analysis": {{
                "short_term_actions": ["immediate actions to take"],
                "long_term_actions": ["long-term development steps"]
            }}
        }}
    ]
}}

Analyze this job description and resume:

JOB DESCRIPTION:
{job_description}

CANDIDATE'S RESUME:
{formatted_sections['skills']}

Experience:
{formatted_sections['experience']}

Education:
{formatted_sections['education']}

Projects:
{formatted_sections['projects']}

IMPORTANT: 
1. Return ONLY valid JSON matching the above structure exactly
2. Use double quotes for all strings
3. Do not include any text outside the JSON object
4. Include gap_analysis only for missing skills
5. Include source only for skills the candidate has"""

    async def analyze(self, job_description: str, resume_data: Dict[str, Any]) -> List[Dict]:
        """Analyze job description against resume data"""
        logger.info("Starting JD analysis")
        
        try:
            # Format resume sections
            logger.info("Formatting resume sections")
            formatted_sections = self._format_resume_sections(resume_data)
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(job_description, formatted_sections)
            logger.info("Created analysis prompt")
            
            # Make API call
            logger.info("Making API call to DeepSeek")
            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert resume analyst. Respond only with the requested JSON structure."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=8000
                )
                
                logger.info("Received response from DeepSeek API")
                logger.info(f"Response object: {response}")
                
                if not hasattr(response, 'choices') or not response.choices:
                    logger.error("No choices in API response")
                    return []
                
                analysis_str = response.choices[0].message.content
                logger.info(f"Raw content from API: {analysis_str}")
                
                if not analysis_str:
                    logger.error("Empty response content")
                    return []
                
                # Clean and parse response
                try:
                    # Remove any markdown formatting
                    clean_str = analysis_str.replace("```json", "").replace("```", "").strip()
                    logger.info(f"Cleaned response string: {clean_str}")
                    
                    # Parse JSON
                    analysis = json.loads(clean_str)
                    logger.info(f"Successfully parsed JSON response: {analysis}")
                    
                    # Extract and validate jd_analysis
                    if 'jd_analysis' in analysis and isinstance(analysis['jd_analysis'], list):
                        logger.info("Valid jd_analysis found in response")
                        
                        # Log success
                        await self.log_ai_request(
                            service_name='jd_analysis',
                            status='success',
                            metadata={
                                'jd_length': len(job_description),
                                'resume_sections': list(resume_data.keys())
                            }
                        )
                        
                        return analysis['jd_analysis']
                    else:
                        logger.error("Missing or invalid jd_analysis in response")
                        return []
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse API response: {str(e)}")
                    logger.error(f"Problematic content: {analysis_str}")
                    return []
                    
            except Exception as api_error:
                logger.error(f"API call failed: {str(api_error)}")
                logger.error(f"Full API error: {type(api_error).__name__}: {str(api_error)}")
                return []
                
        except Exception as e:
            logger.error(f"Analysis process failed: {str(e)}")
            logger.error(f"Full error: {type(e).__name__}: {str(e)}")
            
            # Log failure
            await self.log_ai_request(
                service_name='jd_analysis',
                status='failed',
                metadata={'error': str(e)}
            )
            
            return []