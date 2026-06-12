from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ClaimContext, RuleResult


class PolicyRule(ABC):
    rule_id: str

    @abstractmethod
    def evaluate(self, context: ClaimContext, current_amount: float) -> RuleResult:
        raise NotImplementedError
