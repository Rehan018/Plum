from __future__ import annotations

from .models import AgentStatus, TraceCheck, TraceEvent


def event(
    agent: str,
    status: AgentStatus,
    summary: str,
    checks: list[TraceCheck] | None = None,
    confidence_delta: float = 0.0,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> TraceEvent:
    return TraceEvent(
        agent=agent,
        status=status,
        summary=summary,
        checks=checks or [],
        confidence_delta=confidence_delta,
        warnings=warnings or [],
        errors=errors or [],
    )
