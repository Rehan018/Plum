from __future__ import annotations

from ..models import AgentStatus, ClaimContext, FraudEvaluation, TraceCheck
from ..trace import event
from .base import Agent


class FraudAgent(Agent):
    name = "FraudAgent"

    async def execute(self, context: ClaimContext) -> ClaimContext:
        if context.claim.simulate_component_failure:
            raise RuntimeError("Simulated fraud-service timeout")

        same_day_limit = int(context.policy["fraud_thresholds"]["same_day_claims_limit"])
        high_value_threshold = float(context.policy["fraud_thresholds"]["auto_manual_review_above"])
        same_day_claims = [
            item for item in context.claim.claims_history
            if item.get("date") == context.claim.treatment_date
        ]

        signals = []
        evidence = []
        checks = []

        if len(same_day_claims) > same_day_limit:
            signals.append("SAME_DAY_CLAIM_LIMIT_EXCEEDED")
            same_day_evidence = [
                f"Member has {len(same_day_claims)} prior claims on {context.claim.treatment_date}; this submission is claim #{len(same_day_claims) + 1}.",
                *(f"{claim.get('claim_id')}: Rs {claim.get('amount')} at {claim.get('provider')}" for claim in same_day_claims),
            ]
            evidence.extend(same_day_evidence)
            checks.append(TraceCheck(
                rule_id="SAME_DAY_CLAIM_LIMIT",
                source="policy_terms.json",
                result="WARNING",
                details="Same-day claim frequency exceeds the policy fraud threshold.",
                evidence=same_day_evidence,
            ))
        else:
            checks.append(TraceCheck(
                rule_id="SAME_DAY_CLAIM_LIMIT",
                source="policy_terms.json",
                result="PASSED",
                details="Checked same-day claim frequency.",
                evidence=[f"Prior same-day claims: {len(same_day_claims)}"],
            ))

        bill_total = float(context.extracted.total or 0)
        claimed_amount = float(context.claim.claimed_amount)
        mismatch_threshold = max(500.0, bill_total * 0.10)
        if bill_total and abs(claimed_amount - bill_total) > mismatch_threshold:
            signals.append("CLAIM_AMOUNT_MISMATCH")
            mismatch_evidence = [
                f"Claimed amount: Rs {claimed_amount:.0f}",
                f"Extracted bill total: Rs {bill_total:.0f}",
                f"Mismatch threshold: Rs {mismatch_threshold:.0f}",
            ]
            evidence.extend(mismatch_evidence)
            checks.append(TraceCheck(
                rule_id="CLAIM_AMOUNT_MATCH",
                source="submitted_claim_vs_extracted_bill",
                result="WARNING",
                details="Claimed amount differs materially from extracted bill total.",
                evidence=mismatch_evidence,
            ))
        else:
            checks.append(TraceCheck(
                rule_id="CLAIM_AMOUNT_MATCH",
                source="submitted_claim_vs_extracted_bill",
                result="PASSED",
                details="Claimed amount is consistent with extracted bill total.",
                evidence=[f"Claimed amount: Rs {claimed_amount:.0f}", f"Extracted bill total: Rs {bill_total:.0f}"],
            ))

        if claimed_amount > high_value_threshold:
            signals.append("HIGH_VALUE_CLAIM")
            high_value_evidence = [
                f"Claimed amount: Rs {claimed_amount:.0f}",
                f"Auto manual review threshold: Rs {high_value_threshold:.0f}",
            ]
            evidence.extend(high_value_evidence)
            checks.append(TraceCheck(
                rule_id="HIGH_VALUE_CLAIM",
                source="policy_terms.json",
                result="WARNING",
                details="Claim amount exceeds auto-manual-review threshold.",
                evidence=high_value_evidence,
            ))
        else:
            checks.append(TraceCheck(
                rule_id="HIGH_VALUE_CLAIM",
                source="policy_terms.json",
                result="PASSED",
                details="Claim amount is below auto-manual-review threshold.",
                evidence=[f"Claimed amount: Rs {claimed_amount:.0f}", f"Threshold: Rs {high_value_threshold:.0f}"],
            ))

        signals = list(dict.fromkeys(signals))
        manual_review = bool(signals)
        confidence_delta = -0.1 if signals else 0.0
        context.fraud_evaluation = FraudEvaluation(
            manual_review=manual_review,
            signals=signals,
            evidence=evidence,
            confidence_delta=confidence_delta,
        )
        context.evidence.extend(evidence)
        context.add_trace(event(
            self.name,
            AgentStatus.PARTIAL if signals else AgentStatus.SUCCESS,
            "Fraud checks completed." if not signals else "Fraud or operational risk signals require manual review.",
            checks=checks,
            confidence_delta=confidence_delta,
        ))
        return context
