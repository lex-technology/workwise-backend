from .client import OpenAIClientManager
from utils.parser import ResumeParser
import logging
import json

logger = logging.getLogger(__name__)

class ResumeParserService:
    def __init__(self):
        self.client = OpenAIClientManager().get_client

    async def parse_resume(self, content: bytes, filename: str) -> dict:
        try:
            logger.info("Starting resume parsing process")
            
            # First extract text from the file using ResumeParser
            file_parser = ResumeParser()
            extracted_data = await file_parser.parse_resume(content, filename)
            resume_text = extracted_data['text']
            
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
9. Make sure to extract ALL information from the resume
10. Keep the structure consistent with the output format
11. Note that "sections" is a dictionary, not a list"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Parse this resume:\n\n{resume_text}"}
                ],
                temperature=0.3
            )
            
            parsed_data = self._process_parsing_response(response)
            
            # Add metadata from file parsing
            parsed_data['metadata'] = extracted_data['metadata']
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Resume Parsing Error: {str(e)}")
            raise

    def _process_parsing_response(self, response) -> dict:
        try:
            parsed_data = json.loads(response.choices[0].message.content)
            if "content" not in parsed_data:
                raise ValueError("Invalid response format: missing 'content' key")
            return parsed_data
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error: {str(e)}")
            raise