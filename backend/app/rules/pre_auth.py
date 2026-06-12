from __future__ import annotations

from ..models import ClaimContext, RuleResult, RuleStatus
from .base import PolicyRule


class PreAuthRule(PolicyRule):
    rule_id = "PRE_AUTH_REQUIRED"

    def evaluate(self, context: ClaimContext, current_amount: float) -> RuleResult:
        category = context.claim.claim_category
        if category != "DIAGNOSTIC":
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.PASSED,
                reason="Pre-authorization rule does not apply to this category.",
                evidence=[f"Claim category: {category}"],
                approved_amount=current_amount,
            )

        diagnostic_policy = context.policy["opd_categories"]["diagnostic"]
        threshold = float(diagnostic_policy.get("pre_auth_threshold", 10000))
        high_value_tests = diagnostic_policy.get("high_value_tests_requiring_pre_auth", [])
        descriptions = " ".join([
            " ".join(context.extracted.tests_ordered),
            " ".join(str(item.get("description", "")) for item in context.extracted.line_items),
        ]).lower()
        requires = any(test.lower().split()[0] in descriptions for test in high_value_tests)
        if requires and current_amount > threshold:
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.FAILED,
                reason="Pre-authorization was required for this high-value diagnostic test and was not provided.",
                evidence=[
                    f"High-value diagnostic detected: {descriptions}",
                    f"Amount: Rs {current_amount:.0f}",
                    f"Pre-auth threshold: Rs {threshold:.0f}",
                ],
                approved_amount=0,
                rejected_amount=current_amount,
                rejection_reason="PRE_AUTH_MISSING",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=RuleStatus.PASSED,
            reason="No missing pre-authorization detected.",
            evidence=[f"Amount checked: Rs {current_amount:.0f}"],
            approved_amount=current_amount,
        )
