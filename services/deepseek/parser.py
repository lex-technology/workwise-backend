from datetime import datetime
from typing import Any, Dict, List
import PyPDF2
import io
import docx
import striprtf.striprtf
from pathlib import Path
import logging

# Configure logging
logger = logging.getLogger(__name__)

class ResumeParser:
    def __init__(self):
        self.SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.rtf'}

    async def parse_resume(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse resume content into structured format"""
        try:
            # Validate file type
            file_extension = Path(filename).suffix.lower()
            if file_extension not in self.SUPPORTED_EXTENSIONS:
                raise ValueError(f"Unsupported file type. Supported types: {', '.join(self.SUPPORTED_EXTENSIONS)}")

            # Extract text from file
            text = self._extract_text(content, file_extension)
            
            # Add metadata
            return {
                "metadata": {
                    "original_filename": filename,
                    "file_type": file_extension[1:],
                    "last_modified": datetime.utcnow().isoformat(),
                    "version": 1
                },
                "text": text  # Return extracted text for parser_service to use
            }
            
        except Exception as e:
            logger.error(f"Error parsing resume: {str(e)}")
            raise

    def _extract_text(self, content: bytes, file_extension: str) -> str:
        """Extract text from different file types."""
        try:
            if file_extension == '.pdf':
                return self._extract_pdf_text(content)
            elif file_extension == '.docx':
                return self._extract_docx_text(content)
            elif file_extension == '.txt':
                return content.decode('utf-8')
            elif file_extension == '.rtf':
                return self._extract_rtf_text(content)
        except Exception as e:
            raise ValueError(f"Error extracting text from {file_extension} file: {str(e)}")

    def _extract_pdf_text(self, content: bytes) -> str:
        pdf_file = io.BytesIO(content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text

    def _extract_docx_text(self, content: bytes) -> str:
        docx_file = io.BytesIO(content)
        doc = docx.Document(docx_file)
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return '\n'.join(text)

    def _extract_rtf_text(self, content: bytes) -> str:
        rtf_text = content.decode('utf-8', errors='ignore')
        return striprtf.striprtf(rtf_text)