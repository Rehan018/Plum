from __future__ import annotations

import re
from abc import ABC, abstractmethod

from ..models import AgentStatus, ClaimContext, ExtractionResult, TraceCheck
from ..trace import event
from .base import Agent


class DocumentExtractor(ABC):
    @abstractmethod
    async def extract(self, context: ClaimContext) -> ExtractionResult:
        raise NotImplementedError


class MockStructuredExtractor(DocumentExtractor):
    async def extract(self, context: ClaimContext) -> ExtractionResult:
        extracted = ExtractionResult()
        for doc in context.claim.documents:
            content = doc.content or {}
            patient_name = doc.patient_name_on_doc or content.get("patient_name")
            if patient_name and patient_name not in extracted.patient_names:
                extracted.patient_names.append(patient_name)

            extracted.diagnosis = extracted.diagnosis or content.get("diagnosis")
            extracted.treatment = extracted.treatment or content.get("treatment")
            extracted.hospital_name = extracted.hospital_name or content.get("hospital_name")
            extracted.doctor_name = extracted.doctor_name or content.get("doctor_name")
            extracted.doctor_registration = extracted.doctor_registration or content.get("doctor_registration")
            extracted.tests_ordered.extend(content.get("tests_ordered", []))
            extracted.medicines.extend(content.get("medicines", []))

            if content.get("line_items"):
                extracted.line_items.extend(content["line_items"])
            if content.get("total") is not None:
                extracted.total = float(content["total"])

        extracted.hospital_name = context.claim.hospital_name or extracted.hospital_name
        if extracted.total is None:
            extracted.total = sum(float(item.get("amount", 0)) for item in extracted.line_items) or context.claim.claimed_amount
        return extracted


class LLMDocumentExtractor(DocumentExtractor):
    async def extract(self, context: ClaimContext) -> ExtractionResult:
        raise NotImplementedError("Production extractor would call OCR/vision LLM and validate structured JSON.")


class ExtractionAgent(Agent):
    name = "ExtractionAgent"

    def __init__(self, extractor: DocumentExtractor | None = None) -> None:
        self.extractor = extractor or MockStructuredExtractor()

    async def execute(self, context: ClaimContext) -> ClaimContext:
        extracted = await self.extractor.extract(context)
        extracted.normalized_tags = self._tags(extracted)
        registration_valid = self._valid_registration(extracted.doctor_registration)
        registration_result = "PASSED" if registration_valid else "WARNING"
        registration_details = (
            "Doctor registration number matches known Indian formats."
            if registration_valid
            else "Doctor registration number is missing or does not match known Indian formats."
        )

        context.extracted = extracted
        context.evidence.extend(self._evidence(extracted))
        context.add_trace(event(
            self.name,
            AgentStatus.SUCCESS if registration_valid else AgentStatus.PARTIAL,
            "Structured claim facts extracted from submitted documents.",
            checks=[
                TraceCheck(
                    rule_id="STRUCTURED_EXTRACTION",
                    source=self.extractor.__class__.__name__,
                    result="PASSED",
                    details="Used structured test document content through the extractor contract.",
                    evidence=self._evidence(extracted),
                ),
                TraceCheck(
                    rule_id="DOCTOR_REGISTRATION_FORMAT",
                    source="sample_documents_guide.md",
                    result=registration_result,
                    details=registration_details,
                    evidence=[f"Doctor registration: {extracted.doctor_registration or 'missing'}"],
                ),
            ],
            confidence_delta=0.0 if registration_valid else -0.05,
        ))
        return context

    def _tags(self, extracted: ExtractionResult) -> list[str]:
        haystack = " ".join([
            extracted.diagnosis or "",
            extracted.treatment or "",
            " ".join(extracted.tests_ordered),
            " ".join(str(item.get("description", "")) for item in extracted.line_items),
        ]).lower()
        tags: list[str] = []
        if "diabetes" in haystack:
            tags.append("diabetes")
        if "obesity" in haystack or "bariatric" in haystack or "weight loss" in haystack:
            tags.append("obesity_treatment")
        if "mri" in haystack:
            tags.append("mri")
        if "teeth whitening" in haystack:
            tags.append("cosmetic_dental")
        return tags

    def _evidence(self, extracted: ExtractionResult) -> list[str]:
        evidence = []
        if extracted.patient_names:
            evidence.append(f"Patient name(s): {', '.join(extracted.patient_names)}")
        if extracted.diagnosis:
            evidence.append(f"Diagnosis: {extracted.diagnosis}")
        if extracted.treatment:
            evidence.append(f"Treatment: {extracted.treatment}")
        if extracted.hospital_name:
            evidence.append(f"Provider: {extracted.hospital_name}")
        evidence.append(f"Document total: Rs {extracted.total:.0f}")
        return evidence

    def _valid_registration(self, registration: str | None) -> bool:
        if not registration:
            return False
        standard = r"^(KA|MH|DL|TN|GJ|AP|UP|WB|KL)/\d{5}/\d{4}$"
        ayurveda = r"^AYUR/(KA|MH|DL|TN|GJ|AP|UP|WB|KL)/\d{4,5}/\d{4}$"
        return bool(re.match(standard, registration) or re.match(ayurveda, registration))
