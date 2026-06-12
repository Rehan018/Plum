from __future__ import annotations

from ..models import ClaimContext, RuleResult, RuleStatus
from .base import PolicyRule


class ExclusionRule(PolicyRule):
    rule_id = "EXCLUSION_CHECK"

    def evaluate(self, context: ClaimContext, current_amount: float) -> RuleResult:
        if "obesity_treatment" in context.extracted.normalized_tags:
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.FAILED,
                reason="Obesity, weight loss, and bariatric treatment are excluded under the policy.",
                evidence=[
                    f"Diagnosis: {context.extracted.diagnosis}",
                    f"Treatment: {context.extracted.treatment}",
                    "Policy exclusion: Obesity and weight loss programs / Bariatric surgery",
                ],
                approved_amount=0,
                rejected_amount=current_amount,
                rejection_reason="EXCLUDED_CONDITION",
            )

        if context.claim.claim_category == "DENTAL":
            covered = set(context.policy["opd_categories"]["dental"]["covered_procedures"])
            excluded = {item.lower() for item in context.policy["opd_categories"]["dental"]["excluded_procedures"]}
            approved = 0.0
            rejected = 0.0
            line_results = []
            for item in context.extracted.line_items:
                description = str(item.get("description", ""))
                amount = float(item.get("amount", 0))
                is_excluded = any(term in description.lower() for term in excluded)
                is_covered = any(term.lower() in description.lower() for term in covered)
                if is_excluded or not is_covered:
                    rejected += amount
                    line_results.append({
                        "description": description,
                        "amount": amount,
                        "status": "REJECTED",
                        "reason": "Cosmetic or non-covered dental procedure",
                    })
                else:
                    approved += amount
                    line_results.append({
                        "description": description,
                        "amount": amount,
                        "status": "APPROVED",
                        "reason": "Covered dental procedure",
                    })

            if rejected:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=RuleStatus.WARNING,
                    reason="Some dental line items are excluded and were removed from the payable amount.",
                    evidence=[f"{item['description']}: {item['status']}" for item in line_results],
                    approved_amount=approved,
                    rejected_amount=rejected,
                    line_item_results=line_results,
                )

        return RuleResult(
            rule_id=self.rule_id,
            status=RuleStatus.PASSED,
            reason="No policy exclusion applies.",
            evidence=["No excluded diagnosis, treatment, or line item detected."],
            approved_amount=current_amount,
        )
