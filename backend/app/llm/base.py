"""The only thing pipeline nodes know about a model: "give me an object of this Pydantic type".

Swapping the local model for Claude (or a fake in tests) is a configuration change,
not a change to the pipeline.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model could not produce a valid object (transport error or schema mismatch)."""


class LLMClient(Protocol):
    name: str

    def structured(self, *, system: str, user: str, schema: type[T]) -> T:
        """Return the model's answer parsed and validated as `schema`."""
        ...
