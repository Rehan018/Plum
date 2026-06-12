from __future__ import annotations

from uuid import uuid4

from .agents.base import Agent
from .agents.decision import DecisionAgent
from .agents.document_verification import DocumentVerificationAgent
from .agents.extraction import ExtractionAgent
from .agents.fraud import FraudAgent
from .agents.policy import PolicyAgent
from .models import AgentStatus, ClaimContext, ClaimInput, DecisionResponse, TraceCheck
from .policy_loader import get_member, load_policy
from .trace import event


class ClaimOrchestrator:
    def __init__(self, policy: dict | None = None) -> None:
        self.policy = policy or load_policy()
        self.agents: list[Agent] = [
            DocumentVerificationAgent(),
            ExtractionAgent(),
            PolicyAgent(),
            FraudAgent(),
            DecisionAgent(),
        ]

    async def process(self, claim: ClaimInput) -> DecisionResponse:
        context = ClaimContext(
            claim_id=f"CLM-{uuid4().hex[:8].upper()}",
            claim=claim,
            policy=self.policy,
            member=get_member(self.policy, claim.member_id),
        )
        if context.member:
            context.evidence.append(f"Member: {context.member['name']} ({claim.member_id})")

        for agent in self.agents:
            if context.should_stop and not isinstance(agent, DecisionAgent):
                continue
            try:
                context = await agent.execute(context)
            except Exception as exc:
                context.warnings.append(f"{agent.name} failed: {exc}")
                context.add_trace(event(
                    agent.name,
                    AgentStatus.FAILED,
                    f"{agent.name} failed but the pipeline continued with available data.",
                    checks=[
                        TraceCheck(
                            rule_id="AGENT_FAILURE",
                            source="orchestrator",
                            result="FAILED",
                            details=str(exc),
                            evidence=[f"Failed agent: {agent.name}"],
                        )
                    ],
                    confidence_delta=-0.2,
                    errors=[str(exc)],
                ))
                continue

        if context.decision is None:
            context = await DecisionAgent().execute(context)
        return context.decision
