import requests
import hashlib
from pathlib import Path
import logging
import pytest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"
TEST_TOKEN = "YOUR_JWT_TOKEN"  # Replace with your actual token

class TestResumeParser:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            'Authorization': f'Bearer {TEST_TOKEN}'
        }
        
        # Test resume paths - update these
        self.new_resume_path = '/Users/liongchenglex/Downloads/testscript.docx'
        self.existing_resume_path = '/Users/liongchenglex/Downloads/assistant-project-manager-resume-example.pdf'
        
        # Test data
        self.test_data = {
            'companyApplied': 'Test Company',
            'roleApplied': 'Software Engineer',
            'jobDescription': '''
            We are looking for a Software Engineer with:
            - 5+ years of Python experience
            - FastAPI and REST API design
            - Database design and optimization
            - Strong problem-solving skills
            '''
        }

    def calculate_file_hash(self, file_path):
        """Calculate MD5 hash of file"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def test_health_check(self):
        """Test if server is running"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert 'healthy' in response.json()['status']

    def test_parse_new_resume(self):
        """Test parsing a completely new resume"""
        logger.info("Testing new resume parsing...")
        
        try:
            files = {
                'resume': ('new_resume.pdf', open(self.new_resume_path, 'rb'), 'application/pdf')
            }
            
            response = requests.post(
                f"{BASE_URL}/parse-resume",
                headers=self.headers,
                files=files,
                data=self.test_data
            )
            
            assert response.status_code == 200
            result = response.json()
            
            # Verify response structure
            assert 'resume_id' in result
            assert 'status' in result
            assert 'is_reused' in result
            assert not result['is_reused']  # Should be false for new resume
            
            # Verify resume data was stored correctly
            resume_response = requests.get(
                f"{BASE_URL}/resume/{result['resume_id']}",
                headers=self.headers
            )
            assert resume_response.status_code == 200
            resume_data = resume_response.json()
            
            # Verify required fields
            assert resume_data['company_applied'] == self.test_data['companyApplied']
            assert resume_data['role_applied'] == self.test_data['roleApplied']
            assert resume_data['job_description'] == self.test_data['jobDescription']
            assert 'professional_experience' in resume_data
            
            logger.info(f"New resume parsed successfully. Resume ID: {result['resume_id']}")
            
        except Exception as e:
            logger.error(f"Error in new resume parsing: {str(e)}")
            raise

    def test_parse_existing_resume(self):
        """Test parsing an existing resume (should use cached parse)"""
        logger.info("Testing existing resume parsing...")
        
        try:
            # First parse to create the record
            files = {
                'resume': ('existing_resume.pdf', open(self.existing_resume_path, 'rb'), 'application/pdf')
            }
            
            first_response = requests.post(
                f"{BASE_URL}/parse-resume",
                headers=self.headers,
                files=files,
                data=self.test_data
            )
            
            assert first_response.status_code == 200
            first_result = first_response.json()
            
            # Try parsing the same resume again
            second_response = requests.post(
                f"{BASE_URL}/parse-resume",
                headers=self.headers,
                files=files,
                data=self.test_data
            )
            
            assert second_response.status_code == 200
            second_result = second_response.json()
            
            # Verify it was reused
            assert second_result['is_reused']
            assert second_result['status'] == 'success'
            
            logger.info(f"Existing resume parsed successfully. Resume ID: {second_result['resume_id']}")
            
        except Exception as e:
            logger.error(f"Error in existing resume parsing: {str(e)}")
            raise

    def test_parse_resume_with_id(self):
        """Test parsing using an existing parsed_resume_id"""
        logger.info("Testing resume parsing with parsed_resume_id...")
        
        try:
            # First get a list of parsed resumes
            response = requests.get(
                f"{BASE_URL}/parsed-resumes",
                headers=self.headers
            )
            
            assert response.status_code == 200
            parsed_resumes = response.json()
            
            if not parsed_resumes:
                pytest.skip("No parsed resumes available for testing")
                
            parsed_resume_id = parsed_resumes[0]['id']
            
            # Try creating new resume using existing parsed_resume_id
            data = self.test_data.copy()
            data['parsed_resume_id'] = parsed_resume_id
            
            response = requests.post(
                f"{BASE_URL}/parse-resume",
                headers=self.headers,
                data=data
            )
            
            assert response.status_code == 200
            result = response.json()
            
            assert result['is_reused']
            assert 'resume_id' in result
            
            logger.info(f"Resume created from parsed_resume_id successfully. Resume ID: {result['resume_id']}")
            
        except Exception as e:
            logger.error(f"Error in parsing with parsed_resume_id: {str(e)}")
            raise

    def test_error_handling(self):
        """Test error scenarios"""
        logger.info("Testing error handling...")
        
        try:
            # Test without required fields
            response = requests.post(
                f"{BASE_URL}/parse-resume",
                headers=self.headers,
                data={}
            )
            assert response.status_code in [400, 422]  # FastAPI validation error
            
            # Test with invalid token
            bad_headers = {'Authorization': 'Bearer invalid_token'}
            response = requests.post(
                f"{BASE_URL}/parse-resume",
                headers=bad_headers,
                data=self.test_data
            )
            assert response.status_code == 401
            
        except Exception as e:
            logger.error(f"Error in error handling tests: {str(e)}")
            raise

if __name__ == "__main__":
    pytest.main([__file__, "-v"])