from __future__ import annotations

from ..models import AgentStatus, ClaimContext, PolicyEvaluation, RuleStatus, TraceCheck
from ..rules.copay import CopayRule
from ..rules.exclusion import ExclusionRule
from ..rules.limit import LimitRule
from ..rules.pre_auth import PreAuthRule
from ..rules.waiting_period import WaitingPeriodRule
from ..trace import event
from .base import Agent


class PolicyAgent(Agent):
    name = "PolicyAgent"

    def __init__(self) -> None:
        self.rules = [
            WaitingPeriodRule(),
            ExclusionRule(),
            PreAuthRule(),
            LimitRule(),
            CopayRule(),
        ]

    async def execute(self, context: ClaimContext) -> ClaimContext:
        current_amount = float(context.extracted.total or context.claim.claimed_amount)
        results = []
        checks = []
        rejected_amount = 0.0
        line_item_results = []
        rejection_reasons: list[str] = []

        for rule in self.rules:
            result = rule.evaluate(context, current_amount)
            results.append(result)
            checks.append(TraceCheck(
                rule_id=result.rule_id,
                source="policy_terms.json",
                result=result.status.value,
                details=result.reason,
                evidence=result.evidence,
            ))
            context.evidence.extend(result.evidence)

            if result.line_item_results:
                line_item_results.extend(result.line_item_results)

            if result.rejected_amount:
                rejected_amount += result.rejected_amount

            if result.approved_amount is not None:
                current_amount = float(result.approved_amount)

            if result.rejection_reason:
                rejection_reasons.append(result.rejection_reason)

            if result.status == RuleStatus.FAILED:
                break

        status = AgentStatus.SUCCESS if not rejection_reasons else AgentStatus.PARTIAL
        context.policy_evaluation = PolicyEvaluation(
            rule_results=results,
            approved_amount=round(max(0, current_amount), 2),
            rejected_amount=round(rejected_amount, 2),
            rejection_reasons=rejection_reasons,
            line_item_results=line_item_results,
        )
        context.add_trace(event(
            self.name,
            status,
            "Policy rules evaluated against policy_terms.json.",
            checks=checks,
            confidence_delta=sum(result.confidence_delta for result in results),
        ))
        return context
