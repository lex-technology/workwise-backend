import requests
import time
import logging
import pytest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IjdEQ0xJbnNFOVIvTlU5amkiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3Jxc2RibGxmZ3d6anR1YmtneHJwLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJiNzNiZDI4Ny04YjI2LTRjYjMtYjFmYS0yY2QxN2Y0YWQyMTIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzM4MTQxNjkzLCJpYXQiOjE3MzgxMzgwOTMsImVtYWlsIjoiY2hlbmdsZXgxQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZW1haWwiLCJwcm92aWRlcnMiOlsiZW1haWwiXX0sInVzZXJfbWV0YWRhdGEiOnsiZW1haWwiOiJjaGVuZ2xleDFAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3ViIjoiYjczYmQyODctOGIyNi00Y2IzLWIxZmEtMmNkMTdmNGFkMjEyIn0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3MzgxMzgwOTN9XSwic2Vzc2lvbl9pZCI6ImE0OGY1MTU2LTNkNTItNDgxMy1iZDNjLWE3MzZhMjg3MzhkOCIsImlzX2Fub255bW91cyI6ZmFsc2V9.KfPixJPN2qHcKM5De0C7VaoUip2ovkwtEz8a9XXuBjU" 

class TestJDAnalysis:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            'Authorization': f'Bearer {TEST_TOKEN}'
        }
        
        # We'll get an existing resume ID in the setup
        self.resume_id = self.get_test_resume_id()
    
    def get_test_resume_id(self):
        """Helper to get a valid resume ID for testing"""
        try:
            # Get list of resumes
            response = requests.get(
                f"{BASE_URL}/resume",
                headers=self.headers
            )
            
            if response.status_code == 200:
                resumes = response.json()
                if resumes:
                    return resumes[0]['id']
                    
            pytest.skip("No resumes available for testing")
            
        except Exception as e:
            logger.error(f"Error getting test resume: {str(e)}")
            pytest.skip("Failed to get test resume")

    def test_health_check(self):
        """Test if server is running"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert 'healthy' in response.json()['status']

    def test_jd_analysis_basic(self):
        """Test basic JD analysis functionality"""
        logger.info(f"Testing JD analysis for resume {self.resume_id}...")
        
        try:
            # Trigger JD analysis
            response = requests.post(
                f"{BASE_URL}/analyze-jd/{self.resume_id}",
                headers=self.headers
            )
            
            assert response.status_code == 200
            result = response.json()
            
            # Verify response structure
            assert 'status' in result
            assert 'resume_id' in result
            assert 'analysis' in result
            assert result['resume_id'] == self.resume_id
            
            # Check analysis content
            analysis = result['analysis']
            assert isinstance(analysis, dict)
            
            logger.info("JD analysis started successfully")
            
        except Exception as e:
            logger.error(f"Error in JD analysis: {str(e)}")
            raise

    def test_jd_analysis_completion(self):
        """Test JD analysis completion and result structure"""
        logger.info(f"Testing JD analysis completion for resume {self.resume_id}...")
        
        try:
            # Start analysis
            start_response = requests.post(
                f"{BASE_URL}/analyze-jd/{self.resume_id}",
                headers=self.headers
            )
            assert start_response.status_code == 200
            
            # Poll for completion
            max_attempts = 10
            for attempt in range(max_attempts):
                logger.info(f"Checking analysis status: attempt {attempt + 1}/{max_attempts}")
                
                get_response = requests.get(
                    f"{BASE_URL}/resume/{self.resume_id}",
                    headers=self.headers
                )
                
                if get_response.status_code == 200:
                    data = get_response.json()
                    
                    if data['analysis_status'] == 'completed':
                        # Verify analysis structure
                        assert 'jd_analysis' in data
                        analysis = data['jd_analysis']
                        
                        # Verify required analysis fields
                        expected_fields = [
                            'skills_match',
                            'experience_relevance',
                            'overall_match',
                            'recommendations'
                        ]
                        for field in expected_fields:
                            assert field in analysis, f"Missing field: {field}"
                        
                        logger.info("JD analysis completed successfully")
                        return
                        
                    elif data['analysis_status'] == 'failed':
                        raise AssertionError("JD analysis failed")
                        
                time.sleep(3)
                
            raise TimeoutError("JD analysis timed out")
            
        except Exception as e:
            logger.error(f"Error in JD analysis completion check: {str(e)}")
            raise

    def test_credits_handling(self):
        """Test credits are properly checked and updated"""
        logger.info("Testing credits handling...")
        
        try:
            # Get initial credits
            profile_response = requests.get(
                f"{BASE_URL}/user/profile",
                headers=self.headers
            )
            assert profile_response.status_code == 200
            initial_credits = profile_response.json()['remaining_ai_credits']
            
            # Perform analysis
            analysis_response = requests.post(
                f"{BASE_URL}/analyze-jd/{self.resume_id}",
                headers=self.headers
            )
            assert analysis_response.status_code == 200
            
            # Check credits were deducted
            profile_response = requests.get(
                f"{BASE_URL}/user/profile",
                headers=self.headers
            )
            assert profile_response.status_code == 200
            final_credits = profile_response.json()['remaining_ai_credits']
            
            assert final_credits == initial_credits - 1
            
        except Exception as e:
            logger.error(f"Error in credits handling test: {str(e)}")
            raise

    def test_error_handling(self):
        """Test error scenarios"""
        logger.info("Testing error handling...")
        
        try:
            # Test with invalid resume ID
            response = requests.post(
                f"{BASE_URL}/analyze-jd/999999",
                headers=self.headers
            )
            assert response.status_code == 404
            
            # Test with invalid token
            bad_headers = {'Authorization': 'Bearer invalid_token'}
            response = requests.post(
                f"{BASE_URL}/analyze-jd/{self.resume_id}",
                headers=bad_headers
            )
            assert response.status_code == 401
            
            # Test with insufficient credits
            # First, get a user with no credits
            # This would require setting up a test user with 0 credits
            
        except Exception as e:
            logger.error(f"Error in error handling tests: {str(e)}")
            raise

if __name__ == "__main__":
    pytest.main([__file__, "-v"])