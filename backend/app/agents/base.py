from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ClaimContext


class Agent(ABC):
    name: str

    @abstractmethod
    async def execute(self, context: ClaimContext) -> ClaimContext:
        raise NotImplementedError
