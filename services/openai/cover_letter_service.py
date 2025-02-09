from typing import Dict, List
from .client import OpenAIClientManager

QUESTIONS = [
    {"id": "1", "label": "Company Interest", "question": "What specifically interests you about this company?"},
    {"id": "2", "label": "Relevant Achievements", "question": "What relevant achievements would you like to highlight?"},
    {"id": "3", "label": "Experience Alignment", "question": "How does your experience align with this role?"},
    {"id": "4", "label": "Unique Value", "question": "What unique value can you bring to this position?"}
]

class CoverLetterService:
    def __init__(self):
        self.client = OpenAIClientManager().get_client
        self.questions_map = {q["id"]: q["label"] for q in QUESTIONS}

    async def generate_cover_letter(self, name: str, job_description: str, tone: str, answers: Dict[str, str], experience: List[Dict]):
        try:
            # Format experience into a readable string
            experience_text = self._format_experience(experience)

            # Format answers, only including those that were provided
            answers_text = self._format_answers(answers)

            # Construct the prompt
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
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional cover letter writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating cover letter: {str(e)}")
            raise Exception("Failed to generate cover letter")

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
            
            # Add experience points if they exist
            if 'points' in exp and exp['points']:
                for point in exp['points']:
                    exp_text += f"- {point['text']}\n"
            
            # Add organization description if it exists
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
            if answer.strip():  # Only include non-empty answers
                formatted_answers.append(f"{self.questions_map.get(qid, 'Additional Info')}: {answer}")

        return "\n".join(formatted_answers) 