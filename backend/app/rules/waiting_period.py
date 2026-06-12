from __future__ import annotations

from datetime import date, timedelta

from ..models import ClaimContext, RuleResult, RuleStatus
from .base import PolicyRule


class WaitingPeriodRule(PolicyRule):
    rule_id = "WAITING_PERIOD"

    def evaluate(self, context: ClaimContext, current_amount: float) -> RuleResult:
        member = context.member or {}
        join_date = date.fromisoformat(member.get("join_date", "1900-01-01"))
        treatment_date = date.fromisoformat(context.claim.treatment_date)
        waiting_periods = context.policy["waiting_periods"]["specific_conditions"]

        for tag in context.extracted.normalized_tags:
            if tag in waiting_periods:
                days = int(waiting_periods[tag])
                eligible_from = join_date + timedelta(days=days)
                if treatment_date < eligible_from:
                    return RuleResult(
                        rule_id=self.rule_id,
                        status=RuleStatus.FAILED,
                        reason=f"{tag.replace('_', ' ')} is within the policy waiting period.",
                        evidence=[
                            f"Member join date: {join_date.isoformat()}",
                            f"Treatment date: {treatment_date.isoformat()}",
                            f"Waiting period: {days} days",
                            f"Eligible from: {eligible_from.isoformat()}",
                        ],
                        approved_amount=0,
                        rejected_amount=current_amount,
                        rejection_reason="WAITING_PERIOD",
                    )

        return RuleResult(
            rule_id=self.rule_id,
            status=RuleStatus.PASSED,
            reason="No waiting-period restriction applies.",
            evidence=[f"Treatment date: {context.claim.treatment_date}"],
            approved_amount=current_amount,
        )
