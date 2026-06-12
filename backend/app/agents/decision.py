from __future__ import annotations

from ..models import AgentStatus, ClaimContext, DecisionResponse, DecisionType, TraceCheck
from ..trace import event
from .base import Agent


class DecisionAgent(Agent):
    name = "DecisionAgent"

    async def execute(self, context: ClaimContext) -> ClaimContext:
        if context.decision is not None:
            return context

        policy = context.policy_evaluation
        fraud = context.fraud_evaluation
        failed_agents = [item.agent for item in context.trace if item.status == AgentStatus.FAILED]
        evidence = self._dedupe(context.evidence)

        decision = DecisionType.APPROVED
        approved_amount = policy.approved_amount if policy else float(context.extracted.total or context.claim.claimed_amount)
        next_action = None

        if fraud and fraud.manual_review:
            decision = DecisionType.MANUAL_REVIEW
            approved_amount = 0
            reason = "Claim routed to manual review due to fraud or operational risk signals."
            next_action = "Operations team should review the claim history and provider pattern."
        elif policy and policy.rejection_reasons:
            decision = DecisionType.REJECTED
            approved_amount = 0
            reason = self._rejection_reason(policy.rejection_reasons, evidence)
            next_action = self._next_action(policy.rejection_reasons)
        elif policy and policy.approved_amount > 0 and any(result.status.value == "WARNING" for result in policy.rule_results):
            decision = DecisionType.PARTIAL
            if any(item.get("status") == "REJECTED" for item in policy.line_item_results):
                reason = "Claim partially approved because some line items are excluded by policy."
            else:
                reason = "Claim partially approved because a policy limit capped the payable amount."
        else:
            reason = "Claim approved after document, policy, and fraud checks."

        if failed_agents and decision == DecisionType.APPROVED:
            reason += f" Manual review is recommended because {', '.join(failed_agents)} failed during processing."
            next_action = "Review the claim manually because one pipeline component failed."

        context.add_trace(event(
            self.name,
            AgentStatus.SUCCESS,
            "Final claim outcome generated.",
            checks=[
                TraceCheck(
                    rule_id="FINAL_DECISION",
                    source="agent_outputs",
                    result=decision.value,
                    details=reason,
                    evidence=evidence[:12],
                )
            ],
        ))
        context.decision = DecisionResponse(
            claim_id=context.claim_id,
            decision=decision,
            approved_amount=round(approved_amount, 2),
            confidence_score=context.confidence(),
            reason=reason,
            evidence=evidence,
            next_action=next_action,
            trace=context.trace,
            agent_health=context.agent_health(),
        )
        return context

    def _rejection_reason(self, reasons: list[str], evidence: list[str]) -> str:
        if "WAITING_PERIOD" in reasons:
            eligible = next((item for item in evidence if item.startswith("Eligible from:")), None)
            suffix = f" {eligible}." if eligible else ""
            return f"Claim rejected because the treatment is within the applicable waiting period.{suffix}"
        if "PRE_AUTH_MISSING" in reasons:
            amount = next((item for item in evidence if item.startswith("Amount:")), None)
            threshold = next((item for item in evidence if item.startswith("Pre-auth threshold:")), None)
            details = " ".join(item for item in [amount, threshold] if item)
            return f"Claim rejected because required pre-authorization was not provided. {details}".strip()
        if "PER_CLAIM_EXCEEDED" in reasons:
            return "Claim rejected because the claimed amount exceeds the per-claim limit."
        if "EXCLUDED_CONDITION" in reasons:
            return "Claim rejected because the treatment is excluded under the policy."
        return "Claim rejected by policy rules."

    def _next_action(self, reasons: list[str]) -> str | None:
        if "PRE_AUTH_MISSING" in reasons:
            return "This high-value diagnostic claim requires insurer pre-authorization. Please obtain valid pre-authorization and resubmit the claim with that document."
        return None

    def _dedupe(self, values: list[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result
