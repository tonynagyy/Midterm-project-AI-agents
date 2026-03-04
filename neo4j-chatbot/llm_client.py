import requests
import logging
from config import LLM_PROVIDER, OLLAMA_URL, LLM_MODEL, LLM_TEMPERATURE, OPENAI_API_KEY

logger = logging.getLogger(__name__)

openai_client = None
if LLM_PROVIDER.lower() == "openai":
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        logger.error("OpenAI package is not installed. Please run `pip install openai`.")

class LLMClient:
    def __init__(self):
        self.provider = LLM_PROVIDER.lower()
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.ollama_url = OLLAMA_URL

    def generate(self, prompt: str) -> str:
        """Generates a text response from the configured LLM provider."""
        if self.provider == "openai":
            if not openai_client:
                raise ValueError("OpenAI package is not installed or initialized properly.")
            
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature
            )
            return response.choices[0].message.content.strip()

        elif self.provider == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": self.temperature}
            }
            response = requests.post(self.ollama_url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "").strip()

        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.provider}")
