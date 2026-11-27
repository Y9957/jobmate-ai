from app.llm import LLMClient, get_llm


def llm_client() -> LLMClient:
    """FastAPI dependency for the model. Tests override it with a scripted FakeLLM."""
    return get_llm()
