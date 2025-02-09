from .client import DeepSeekClientManager
from .parser import ResumeParser
import logging
from ..base_service import BaseService
from typing import Optional
import json

logger = logging.getLogger(__name__)

class ResumeParserService(BaseService):
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)
        self.client = DeepSeekClientManager().get_client

    async def parse_resume(self, content: bytes, filename: str) -> dict:
        try:
            print("🔍 Starting resume parsing process")
            logger.info("Starting resume parsing process")
            
            # First extract text from the file using ResumeParser
            print(f"📄 Attempting to parse file: {filename}")
            file_parser = ResumeParser()
            extracted_data = await file_parser.parse_resume(content, filename)
            resume_text = extracted_data['text']
            metadata = extracted_data['metadata']

            print(f"📝 Extracted text length: {len(resume_text)}")
            logger.info(f"Extracted text length: {len(resume_text)}")
            if not resume_text.strip():
                print("❌ No text was extracted from the resume")
                raise ValueError("No text was extracted from the resume")
            
            print("🔄 Formatting resume text for prompt")
            # Make sure the resume text is properly formatted for the prompt
            formatted_resume = resume_text.replace('"', '\\"').replace('\n', '\\n')
            
            print("🤖 Sending to AI for parsing")
            system_prompt = """You are an expert resume parser. Your task is to extract and organize information from the resume into a structured format.

OUTPUT FORMAT:
{
    "content": {
        "sections": [
            {
                "type": "contact_information",
                "content": {
                    "name": "",
                    "email": "",
                    "phone": "",
                    "location": "",
                    "linkedin": "",
                    "residency_status": ""
                }
            },
            {
                "type": "executive summary": "",
                "content": ""
            },
            {
                "type": "professional_experience",
                "entries": [
                    {
                        "organization": "",
                        "role": "",
                        "duration": "",
                        "location": "",
                        "orgnazation_description": "",
                        "points": [
                            "bullet point 1",
                            "bullet point 2"
                        ]
                    }
                ]
            },
            {
                "type": "education",
                "entries": [
                    {
                        "institution": "",
                        "degree": "",
                        "duration": "",
                        "grade": "",
                        "relevant_courses": []
                    }
                ]
            },
            {
                "type": "skills",
                    "entries": [
                    {
                        "technical_skills": "",
                        "soft_skills": ""
                    }
                ]
            },
            {
                "type": "certificates", # ONLY IF CERTIFICATES SECTION IS PRESENT
                "entries": [
                    {
                        "name": "",
                        "issuer": "",
                        "date_acquired": "",
                        "expiry_date": ""
                    }
                ]
            },
            {
                "type": "personal_projects",
                "entries": [
                    {
                        "project_name": "",
                        "project_description": "",
                        "project_experience": [
                            "bullet point 1",
                            "bullet point 2"
                        ],
                        "technologies_used": [],
                        "github_link": ""  
                    }
                ]
            },
            {
                "type": "miscellaneous",  #FOR ANYTHING NOT EXPECTED
                "entries": [
                    {
                        "label": "",
                        "value": "",
                        "type": "text|list|link|contact"
                    }
                ]
            }
        ]
    }
}

PARSING GUIDELINES:
1. Extract all contact information accurately
2. Maintain chronological order within sections
3. Create separate entries for each job position and education
4. Preserve the original text in bullet points
5. Ensure all dates are in a consistent format (MM/YYYY)
6. Extract skills as individual entries
7. Do not summarise the professional experience bullet points
8. If you cannot find any information, leave it blank
9. Language skillsshould be miscellaneous
10. Make sure to extract ALL information from the resume
11. Keep the structure consistent with the output format
12. Note that "sections" is a dictionary, not a list"""
            
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Parse this resume:\n\n{resume_text}"}
                ],
                temperature=0.3
            )
            
            print("✨ Processing AI response")
            parsed_data = self._process_parsing_response(response)
            
            print("📊 Adding metadata from file parsing")
            # Add metadata from file parsing
            await self.log_ai_request(
                service_name='resume_parsing',
                status='success',
                metadata={
                    'filename': filename,
                    'content_length': len(resume_text)
                }
            )
            
            print("✅ Resume parsing completed successfully")
            return {
                'parsed_data': parsed_data,
                'metadata': metadata
            }
            
        except Exception as e:
            print(f"❌ Resume Parsing Error: {str(e)}")
            await self.log_ai_request(
                service_name='resume_parsing',
                status='failed',
                metadata={'error': str(e)}
            )
            logger.error(f"Resume Parsing Error: {str(e)}")
            raise

    def _process_parsing_response(self, response) -> dict:
        try:
            # Get raw content
            content = response.choices[0].message.content
            logger.info("Raw API Response Content:")
            logger.info(content)
            
            # Clean markdown formatting
            cleaned_content = content.strip()
            cleaned_content = cleaned_content.replace('```json', '').replace('```', '').strip()
            logger.info("Cleaned content:")
            logger.info(cleaned_content)
            
            # Parse JSON
            parsed_data = json.loads(cleaned_content)
            
            if "content" not in parsed_data:
                raise ValueError("Invalid response format: missing 'content' key")
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error: {str(e)}")
            logger.error("Failed content:")
            logger.error(content)
            raise