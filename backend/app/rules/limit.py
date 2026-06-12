from __future__ import annotations

from ..models import ClaimContext, RuleResult, RuleStatus
from .base import PolicyRule


class LimitRule(PolicyRule):
    rule_id = "LIMIT_CHECK"

    def evaluate(self, context: ClaimContext, current_amount: float) -> RuleResult:
        per_claim_limit = float(context.policy["coverage"]["per_claim_limit"])
        annual_opd_limit = float(context.policy["coverage"]["annual_opd_limit"])
        ytd_after_claim = context.claim.ytd_claims_amount + current_amount

        if context.claim.claim_category == "CONSULTATION" and current_amount > per_claim_limit:
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.FAILED,
                reason="Claimed amount exceeds the per-claim limit.",
                evidence=[
                    f"Claimed amount: Rs {current_amount:.0f}",
                    f"Per-claim limit: Rs {per_claim_limit:.0f}",
                ],
                approved_amount=0,
                rejected_amount=current_amount,
                rejection_reason="PER_CLAIM_EXCEEDED",
            )

        if ytd_after_claim > annual_opd_limit:
            allowed = max(0, annual_opd_limit - context.claim.ytd_claims_amount)
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.WARNING,
                reason="Annual OPD limit partially caps the payable amount.",
                evidence=[
                    f"YTD before claim: Rs {context.claim.ytd_claims_amount:.0f}",
                    f"Annual OPD limit: Rs {annual_opd_limit:.0f}",
                    f"Allowed remaining amount: Rs {allowed:.0f}",
                ],
                approved_amount=allowed,
                rejected_amount=max(0, current_amount - allowed),
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=RuleStatus.PASSED,
            reason="Claim is within applicable limits.",
            evidence=[
                f"Amount checked: Rs {current_amount:.0f}",
                f"Annual OPD limit: Rs {annual_opd_limit:.0f}",
            ],
            approved_amount=current_amount,
        )
