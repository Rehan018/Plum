from __future__ import annotations

from ..models import ClaimContext, RuleResult, RuleStatus
from .base import PolicyRule


class CopayRule(PolicyRule):
    rule_id = "COPAY_AND_NETWORK_DISCOUNT"

    def evaluate(self, context: ClaimContext, current_amount: float) -> RuleResult:
        category_key = context.claim.claim_category.lower()
        category_policy = context.policy["opd_categories"].get(category_key, {})
        amount = current_amount
        evidence = [f"Starting payable amount: Rs {amount:.0f}"]

        hospital = context.extracted.hospital_name or context.claim.hospital_name
        network_hospitals = {name.lower() for name in context.policy["network_hospitals"]}
        network_discount = float(category_policy.get("network_discount_percent", 0))
        if hospital and hospital.lower() in network_hospitals and network_discount:
            discount = amount * network_discount / 100
            amount -= discount
            evidence.append(f"Network hospital: {hospital}")
            evidence.append(f"Network discount {network_discount:.0f}% deducted: Rs {discount:.0f}")

        copay = float(category_policy.get("copay_percent", 0))
        if copay:
            deduction = amount * copay / 100
            amount -= deduction
            evidence.append(f"Co-pay {copay:.0f}% deducted after discounts: Rs {deduction:.0f}")

        return RuleResult(
            rule_id=self.rule_id,
            status=RuleStatus.PASSED,
            reason="Discounts and co-pay applied according to policy terms.",
            evidence=evidence + [f"Final payable amount: Rs {amount:.0f}"],
            approved_amount=round(amount, 2),
            rejected_amount=max(0, current_amount - amount),
        )
