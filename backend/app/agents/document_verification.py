from __future__ import annotations

from collections import Counter

from ..models import AgentStatus, ClaimContext, DecisionResponse, DecisionType, TraceCheck
from ..trace import event
from .base import Agent


class DocumentVerificationAgent(Agent):
    name = "DocumentVerificationAgent"

    async def execute(self, context: ClaimContext) -> ClaimContext:
        claim = context.claim
        if claim.policy_id != context.policy.get("policy_id"):
            message = f"Policy ID {claim.policy_id} does not match the active policy {context.policy.get('policy_id')}."
            return self._block(context, message, [
                TraceCheck(
                    rule_id="POLICY_ID_MISMATCH",
                    source="policy_terms.json",
                    result="FAILED",
                    details=message,
                    evidence=[f"Submitted policy_id: {claim.policy_id}", f"Expected policy_id: {context.policy.get('policy_id')}"],
                )
            ])

        if context.member is None:
            message = f"Member ID {claim.member_id} was not found in the policy roster."
            return self._block(context, message, [
                TraceCheck(
                    rule_id="MEMBER_NOT_FOUND",
                    source="policy_terms.json",
                    result="FAILED",
                    details=message,
                    evidence=[f"Submitted member_id: {claim.member_id}"],
                )
            ])

        if claim.claim_category not in context.policy["document_requirements"]:
            valid_categories = ", ".join(sorted(context.policy["document_requirements"].keys()))
            message = f"Claim category {claim.claim_category} is not supported by this policy."
            return self._block(context, message, [
                TraceCheck(
                    rule_id="UNKNOWN_CLAIM_CATEGORY",
                    source="policy_terms.json",
                    result="FAILED",
                    details=message,
                    evidence=[f"Submitted category: {claim.claim_category}", f"Supported categories: {valid_categories}"],
                )
            ])

        requirements = context.policy["document_requirements"][claim.claim_category]
        required = set(requirements["required"])
        uploaded_types = [doc.actual_type for doc in claim.documents]
        uploaded = set(uploaded_types)

        unreadable = [doc for doc in claim.documents if (doc.quality or "").upper() == "UNREADABLE"]
        if unreadable:
            doc = unreadable[0]
            message = (
                f"{doc.actual_type} document {doc.file_name or doc.file_id} cannot be read. "
                "Please re-upload a clearer image or PDF of that specific document."
            )
            return self._block(context, message, [
                TraceCheck(
                    rule_id="DOCUMENT_READABILITY",
                    source="submitted_documents",
                    result="FAILED",
                    details=message,
                    evidence=[f"Unreadable document: {doc.file_id}", f"Document type: {doc.actual_type}"],
                )
            ], confidence_delta=-0.25)

        missing = sorted(required - uploaded)
        if missing:
            counts = Counter(uploaded_types)
            uploaded_summary = ", ".join(f"{count} x {doc_type}" for doc_type, count in counts.items()) or "no documents"
            message = (
                f"{claim.claim_category} claims require {', '.join(sorted(required))}. "
                f"You uploaded {uploaded_summary}; missing required document type: {', '.join(missing)}."
            )
            return self._block(context, message, [
                TraceCheck(
                    rule_id="REQUIRED_DOCUMENTS",
                    source="policy_terms.json",
                    result="FAILED",
                    details=message,
                    evidence=[f"Required: {', '.join(sorted(required))}", f"Uploaded: {uploaded_summary}"],
                )
            ])

        patient_names: dict[str, str] = {}
        normalized_patient_names: dict[str, str] = {}
        for doc in claim.documents:
            content_name = (doc.content or {}).get("patient_name")
            name = doc.patient_name_on_doc or content_name
            if name:
                patient_names[doc.file_id] = name
                normalized_patient_names[doc.file_id] = self._normalize_name(name)

        distinct_names = sorted(set(normalized_patient_names.values()))
        if len(distinct_names) > 1:
            evidence = [f"{file_id}: {name}" for file_id, name in patient_names.items()]
            message = "Documents appear to belong to different patients: " + "; ".join(evidence)
            return self._block(context, message, [
                TraceCheck(
                    rule_id="PATIENT_NAME_CONSISTENCY",
                    source="submitted_documents",
                    result="FAILED",
                    details=message,
                    evidence=evidence,
                )
            ], confidence_delta=-0.1)

        context.add_trace(event(
            self.name,
            AgentStatus.SUCCESS,
            "All required documents are present and readable.",
            checks=[
                TraceCheck(
                    rule_id="REQUIRED_DOCUMENTS",
                    source="policy_terms.json",
                    result="PASSED",
                    details=f"Found required documents for {claim.claim_category}: {', '.join(sorted(required))}.",
                    evidence=[f"Uploaded types: {', '.join(uploaded_types)}"],
                )
            ],
        ))
        return context

    def _normalize_name(self, name: str) -> str:
        return " ".join(name.strip().lower().split())

    def _block(
        self,
        context: ClaimContext,
        message: str,
        checks: list[TraceCheck],
        confidence_delta: float = 0.0,
    ) -> ClaimContext:
        context.blocked_reason = message
        context.should_stop = True
        context.evidence.extend(evidence for check in checks for evidence in check.evidence)
        context.add_trace(event(self.name, AgentStatus.BLOCKED, message, checks, confidence_delta=confidence_delta))
        context.decision = DecisionResponse(
            claim_id=context.claim_id,
            decision=DecisionType.BLOCKED,
            approved_amount=0,
            confidence_score=context.confidence(),
            reason=message,
            evidence=context.evidence,
            next_action="Correct the document issue and resubmit the claim.",
            trace=context.trace,
            agent_health=context.agent_health(),
        )
        return context
