import requests
import logging
from config import LLM_PROVIDER, OLLAMA_URL, LLM_MODEL, LLM_TEMPERATURE, OPENAI_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-initialize provider clients at module load
# ---------------------------------------------------------------------------
openai_client = None
groq_client = None

if LLM_PROVIDER.lower() == "openai":
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized.")
    except ImportError:
        logger.error("OpenAI package not installed. Run: pip install openai")

elif LLM_PROVIDER.lower() == "groq":
    try:
        from openai import OpenAI  # Groq uses the OpenAI-compatible SDK
        groq_client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        logger.info("Groq client initialized.")
    except ImportError:
        logger.error("OpenAI package (required for Groq) not installed. Run: pip install openai")


# ---------------------------------------------------------------------------
# Unified LLM Client
# ---------------------------------------------------------------------------
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
                raise ValueError(
                    "OpenAI client not initialized. Check OPENAI_API_KEY and package installation."
                )
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()

        elif self.provider == "groq":
            if not groq_client:
                raise ValueError(
                    "Groq client not initialized. Check GROQ_API_KEY and package installation."
                )
            response = groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()

        elif self.provider == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": self.temperature},
            }
            try:
                response = requests.post(self.ollama_url, json=payload, timeout=120)
                response.raise_for_status()
                return response.json().get("response", "").strip()
            except requests.exceptions.ConnectionError:
                raise ConnectionError(
                    f"Could not connect to Ollama at {self.ollama_url}. Is Ollama running?"
                )
            except requests.exceptions.Timeout:
                raise TimeoutError("Ollama request timed out after 120 seconds.")

        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: '{self.provider}'. "
                "Valid options are: 'openai', 'groq', 'ollama'"
            )
