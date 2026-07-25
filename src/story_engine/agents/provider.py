"""Small model-provider abstraction; selection stays in runtime configuration."""

from __future__ import annotations

from typing import Protocol


class ModelProvider(Protocol):
    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str: ...
