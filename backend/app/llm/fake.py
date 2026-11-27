from collections import defaultdict, deque
from collections.abc import Callable

from pydantic import BaseModel

from app.llm.base import LLMError, T

Responder = BaseModel | Callable[[str, str], BaseModel]


class FakeLLM:
    """Scripted model for tests: queue answers per output type, record every call.

    A queued item is either a ready object or a function (system, user) -> object,
    so a test can answer based on what the pipeline actually asked.
    """

    name = "fake"

    def __init__(self) -> None:
        self._queues: dict[type[BaseModel], deque[Responder]] = defaultdict(deque)
        self.calls: list[tuple[str, str, str]] = []  # (schema name, system, user)

    def queue(self, schema: type[BaseModel], *answers: Responder) -> "FakeLLM":
        self._queues[schema].extend(answers)
        return self

    def structured(self, *, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((schema.__name__, system, user))
        if not self._queues[schema]:
            raise LLMError(f"FakeLLM has no queued answer for {schema.__name__}")
        answer = self._queues[schema].popleft()
        result = answer(system, user) if callable(answer) else answer
        return schema.model_validate(result.model_dump())

    def count(self, schema: type[BaseModel]) -> int:
        return sum(1 for name, _, _ in self.calls if name == schema.__name__)
