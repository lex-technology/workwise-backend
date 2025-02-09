from openai import OpenAI
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class DeepSeekClientManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                api_key = os.getenv("DEEPSEEK_API_KEY")  # Update environment variable key
                if not api_key:
                    raise ValueError("DeepSeek API key not found")
                
                # Initialize the OpenAI client with DeepSeek's base URL
                cls._instance.client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1"  # Use DeepSeek's base URL
                )
                logger.info("DeepSeek client initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing DeepSeek client: {str(e)}")
                raise
        return cls._instance

    @property
    def get_client(self):
        return self.client