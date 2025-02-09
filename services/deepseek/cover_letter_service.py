from typing import Dict, List, Optional
from .client import DeepSeekClientManager
from services.base_service import BaseService
from fastapi import HTTPException
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

QUESTIONS = [
    {"id": "1", "label": "Company Interest", "question": "What specifically interests you about this company?"},
    {"id": "2", "label": "Relevant Achievements", "question": "What relevant achievements would you like to highlight?"},
    {"id": "3", "label": "Experience Alignment", "question": "How does your experience align with this role?"},
    {"id": "4", "label": "Unique Value", "question": "What unique value can you bring to this position?"}
]

class CoverLetterService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        self.client = DeepSeekClientManager().get_client
        self.questions_map = {q["id"]: q["label"] for q in QUESTIONS}
        self.requires_credits = True

    async def get_professional_experience(self, resume_id: int) -> List[Dict]:
        """Get professional experience from Supabase"""
        try:
            # First get the experience entries
            experiences = self.supabase.from_('professional_experiences')\
                .select('*')\
                .eq('resume_id', resume_id)\
                .execute()
            
            if not experiences.data:
                return []

            # For each experience, get its points
            result = []
            for exp in experiences.data:
                points = self.supabase.from_('experience_points')\
                    .select('*')\
                    .eq('experience_id', exp['id'])\
                    .execute()
                
                exp_dict = dict(exp)
                exp_dict['points'] = points.data if points.data else []
                result.append(exp_dict)

            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching professional experience: {str(e)}")

    async def generate_cover_letter(self, resume_id: int, job_description: str, 
                                  tone: str, answers: Dict[str, str]):
        try:
            # Check credits before proceeding
            has_credits = await self.check_credits()
            if not has_credits:
                raise HTTPException(status_code=402, detail="Insufficient credits")

            # Get resume data
            resume = self.supabase.from_('resumes')\
                .select('contact_information')\
                .eq('id', resume_id)\
                .single()\
                .execute()

            if not resume.data:
                raise HTTPException(status_code=404, detail="Resume not found")

            contact_info = resume.data['contact_information']
            experience = await self.get_professional_experience(resume_id)

            # Generate cover letter
            cover_letter = await self._generate_cover_letter_content(
                name=contact_info.get('name', ''),
                job_description=job_description,
                tone=tone,
                answers=answers,
                experience=experience
            )

            # Create metadata
            metadata = {
                'tone': tone,
                'answers': answers,
                'generated_at': datetime.now().isoformat()
            }

            # Update resume with new cover letter
            self.supabase.from_('resumes')\
                .update({
                    'cover_letter': cover_letter,
                    'metadata': metadata
                })\
                .eq('id', resume_id)\
                .execute()

            # Log the AI request
            self.log_ai_request(
                service_name="cover_letter_generation",
                status="success",
                metadata={"resume_id": resume_id}
            )

            return {
                "cover_letter": cover_letter,
                "metadata": metadata
            }

        except Exception as e:
            # Log failed attempt
            self.log_ai_request(
                service_name="cover_letter_generation",
                status="error",
                metadata={"error": str(e)}
            )
            raise

    async def get_cover_letter(self, resume_id: int):
        try:
            logger.info(f"Getting cover letter for resume_id: {resume_id}")
            
            # Get the resume data
            query_result = self.supabase.from_('resumes')\
                .select('cover_letter, metadata')\
                .eq('id', resume_id)\
                .single()\
                .execute()

            logger.info(f"Query result: {query_result}")

            # Check if query_result exists
            if not query_result:
                logger.error("Query result is None")
                return {
                    "cover_letter": "",
                    "tone": "professional",
                    "answers": {}
                }

            # Check if data exists
            if not hasattr(query_result, 'data') or not query_result.data:
                logger.error("No data in query result")
                return {
                    "cover_letter": "",
                    "tone": "professional",
                    "answers": {}
                }

            # Safely get data
            data = query_result.data
            logger.info(f"Retrieved data: {data}")

            # Handle cover_letter - return empty string if None
            cover_letter = data.get('cover_letter')
            if cover_letter is None:
                cover_letter = ""

            # Safely build response
            response = {
                "cover_letter": cover_letter,
                "tone": "personal",  # default tone
                "answers": {}  # default empty answers
            }

            # Safely add metadata if it exists
            metadata = data.get('metadata')
            if metadata:
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                response["tone"] = metadata.get('tone', 'professional')
                response["answers"] = metadata.get('answers', {})

            logger.info(f"Returning response: {response}")
            return response

        except Exception as e:
            logger.error(f"Error in get_cover_letter: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving cover letter: {str(e)}"
            )

        except Exception as e:
            logger.error(f"Error in get_cover_letter: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving cover letter: {str(e)}"
            )

    async def save_cover_letter(self, resume_id: int, edited_letter: str):
        try:
            # First get existing resume data including metadata
            existing_resume = self.supabase.from_('resumes')\
            .select('metadata')\
            .eq('id', resume_id)\
            .single()\
            .execute()
            
            if not existing_resume.data:
                raise HTTPException(status_code=404, detail="Resume not found")

            # Get existing metadata or initialize empty dict if none
            existing_metadata = existing_resume.data.get('metadata', {}) or {}
            
            # Merge new metadata with existing
            updated_metadata = {
                **existing_metadata,  # Keep all existing metadata
                'last_edited': datetime.now().isoformat(),
                'edited_by_user': True
            }

            # Update with merged metadata
            update_data = {
                'cover_letter': edited_letter,
                'metadata': updated_metadata
            }

            result = self.supabase.from_('resumes')\
                .update(update_data)\
                .eq('id', resume_id)\
                .execute()

            if hasattr(result, 'error') and result.error:
                raise HTTPException(status_code=400, detail=f"Supabase error: {result.error}")

            return {"message": "Cover letter updated successfully"}

        except Exception as e:
            print(f"Error in save_cover_letter: {str(e)}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=500, 
                detail=f"Error saving cover letter: {str(e)}"
            )
            # Prepare update data
       

    async def _generate_cover_letter_content(self, name: str, job_description: str, 
                                           tone: str, answers: Dict[str, str], 
                                           experience: List[Dict]) -> str:
        """Internal method to generate cover letter content using DeepSeek"""
        try:
            experience_text = self._format_experience(experience)
            answers_text = self._format_answers(answers)

            tone_instructions = {
                'personal': 'Write in a friendly and personable tone',
                'professional': 'Write in a formal and business-like tone',
                'enthusiastic': 'Write in a high-energy and passionate tone',
                'confident': 'Write in a strong and assertive tone'
            }

            prompt = f"""
            Write a cover letter for {name} based on the following information:

            Job Description:
            {job_description}

            Professional Experience:
            {experience_text}

            {answers_text}

            Tone Instructions: {tone_instructions.get(tone, tone_instructions['professional'])}

            Guidelines:
            - Keep it concise and impactful
            - Address specific points from the job description
            - Highlight relevant experience and achievements
            - Maintain a professional yet engaging style
            - Include a strong opening and closing
            - Format with proper spacing and paragraphs
            """

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a professional cover letter writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise Exception(f"Failed to generate cover letter: {str(e)}")

    def _format_experience(self, experience: List[Dict]) -> str:
        """Format the professional experience into a readable string."""
        if not experience:
            return "No previous experience provided."

        formatted_text = []
        for exp in experience:
            exp_text = f"""
            {exp['organization']} - {exp['role']}
            Duration: {exp['duration']}
            Location: {exp['location']}
            Key Achievements:
            """
            
            if exp.get('points'):
                for point in exp['points']:
                    exp_text += f"- {point['text']}\n"
            
            if exp.get('organization_description'):
                exp_text += f"\nOrganization: {exp['organization_description']}\n"
            
            formatted_text.append(exp_text)

        return "\n\n".join(formatted_text)

    def _format_answers(self, answers: Dict[str, str]) -> str:
        """Format the provided answers into a readable string."""
        if not answers:
            return "Additional Context: None provided"

        formatted_answers = ["Additional Context:"]
        for qid, answer in answers.items():
            if answer.strip():
                formatted_answers.append(f"{self.questions_map.get(qid, 'Additional Info')}: {answer}")

        return "\n".join(formatted_answers)