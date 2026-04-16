import requests
import logging
from config import (
    LLM_PROVIDER,
    OLLAMA_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS_DEFAULT,
    OPENAI_API_KEY,
    GROQ_API_KEY,
    LMSTUDIO_URL
)

try:
    from langsmith import traceable
except Exception:  # pragma: no cover
    def traceable(*_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator

logger = logging.getLogger(__name__)

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
        from openai import OpenAI 
        groq_client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        logger.info("Groq client initialized.")
    except ImportError:
        logger.error("OpenAI package (required for Groq) not installed. Run: pip install openai")


class LLMClient:
    def __init__(self):
        self.provider = LLM_PROVIDER.lower()
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.default_max_tokens = max(1, LLM_MAX_TOKENS_DEFAULT)
        self.ollama_url = OLLAMA_URL
        self.lmstudio_url = globals().get("LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")

    @traceable(name="llm_generate", run_type="llm")
    def generate(self, prompt: str, max_tokens: int | None = None) -> str:
        """Generates a text response from the configured LLM provider."""
        token_cap = max(1, int(max_tokens or self.default_max_tokens))
        logger.debug(
            "Calling LLM provider=%s model=%s max_tokens=%s",
            self.provider,
            self.model,
            token_cap,
        )

        if self.provider == "openai":
            if not openai_client:
                raise ValueError(
                    "OpenAI client not initialized. Check OPENAI_API_KEY and package installation."
                )
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=token_cap,
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
                max_tokens=token_cap,
            )
            return response.choices[0].message.content.strip()

        elif self.provider == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": token_cap,
                },
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

        elif self.provider == "lmstudio":
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": token_cap,
                "stream": False,
            }
            try:
                response = requests.post(self.lmstudio_url, json=payload, timeout=120)
                response.raise_for_status()
                # LM Studio returns OpenAI-compatible response
                return response.json()["choices"][0]["message"]["content"].strip()
            except requests.exceptions.ConnectionError:
                raise ConnectionError(
                    f"Could not connect to LM Studio at {self.lmstudio_url}. Is LM Studio running?"
                )
            except requests.exceptions.Timeout:
                raise TimeoutError("LM Studio request timed out after 120 seconds.")

        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: '{self.provider}'. "
                "Valid options are: 'openai', 'groq', 'ollama', 'lmstudio'"
            )
