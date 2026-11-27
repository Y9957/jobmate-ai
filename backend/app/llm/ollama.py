import httpx
from pydantic import ValidationError

from app.llm.base import LLMError, T


class OllamaClient:
    """Local model through Ollama's /api/chat with a JSON-schema constrained output."""

    def __init__(self, base_url: str, model: str, num_ctx: int = 8192, timeout: float = 300.0, retries: int = 1):
        self.name = f"ollama:{model}"
        self._model = model
        self._num_ctx = num_ctx
        self._retries = retries
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def structured(self, *, system: str, user: str, schema: type[T]) -> T:
        body = {
            "model": self._model,
            "stream": False,
            "think": False,
            "format": schema.model_json_schema(),
            "options": {"temperature": 0, "num_ctx": self._num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        last_error: Exception | None = None
        for _ in range(self._retries + 1):
            try:
                resp = self._http.post("/api/chat", json=body)
                resp.raise_for_status()
                return schema.model_validate_json(resp.json()["message"]["content"])
            except (httpx.HTTPError, KeyError, ValidationError) as e:
                last_error = e
        raise LLMError(f"{self.name} failed to return a valid {schema.__name__}: {last_error}") from last_error
