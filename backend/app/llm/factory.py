from app.config import Settings, get_settings
from app.llm.base import LLMClient
from app.llm.ollama import OllamaClient


def get_llm(settings: Settings | None = None) -> LLMClient:
    s = settings or get_settings()
    if s.llm_provider == "ollama":
        return OllamaClient(s.ollama_base_url, s.ollama_model, s.ollama_num_ctx, s.llm_timeout_seconds)
    raise ValueError(f"Unknown llm_provider: {s.llm_provider!r}")
