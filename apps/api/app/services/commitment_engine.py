from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from app.models import AutomationTriggerType
from app.models.common import utc_now
from app.repositories.commitments import CommitmentRepository
from app.schemas.commitments import (
    CommitmentAssessmentResponse,
    CommitmentImpactResponse,
    CommitmentWarningsResponse,
)
from app.services.automation import dispatch_automation_event
from app.services.commitment_collectors import collect_commitment_evidence
from app.services.commitment_evaluators import build_commitment_impact, evaluate_commitment
from app.services.commitment_management import commitment_responses


def assess_commitment(
    session: Session,
    commitment_id: UUID,
) -> CommitmentAssessmentResponse:
    calculated_at = utc_now()
    evidence = collect_commitment_evidence(session, commitment_id)
    impact = build_commitment_impact(evidence, now=calculated_at)
    components, overall, warnings, actions, assumptions = evaluate_commitment(evidence, impact)
    commitment = commitment_responses(
        CommitmentRepository(session),
        [evidence.commitment],
    )[0]
    assessment = CommitmentAssessmentResponse(
        commitment=commitment,
        impact=impact,
        time_capacity_status=components["time"],
        financial_capacity_status=components["financial"],
        dependency_status=components["dependency"],
        schedule_conflict_status=components["schedule"],
        goal_impact_status=components["goal"],
        deadline_status=components["deadline"],
        overall_status=overall,
        warnings=warnings,
        assumptions=assumptions,
        suggested_actions=actions,
        calculated_at=calculated_at,
    )
    for warning in assessment.warnings:
        dispatch_automation_event(
            session,
            AutomationTriggerType.COMMITMENT_WARNING_CREATED,
            context={
                "entity_type": "commitment",
                "entity_id": str(commitment.id),
                "commitment_title": commitment.title,
                "warning_code": warning.code,
                "severity": warning.severity.value,
            },
            source_key=f"commitment:{commitment.id}:{commitment.revision}:{warning.code}",
        )
    return assessment


def get_commitment_impact(
    session: Session,
    commitment_id: UUID,
) -> CommitmentImpactResponse:
    evidence = collect_commitment_evidence(session, commitment_id)
    return build_commitment_impact(evidence)


def get_commitment_warnings(
    session: Session,
    commitment_id: UUID,
) -> CommitmentWarningsResponse:
    assessment = assess_commitment(session, commitment_id)
    return CommitmentWarningsResponse(
        commitment_id=commitment_id,
        overall_status=assessment.overall_status,
        warnings=assessment.warnings,
        suggested_actions=assessment.suggested_actions,
        assumptions=assessment.assumptions,
        calculated_at=assessment.calculated_at,
    )
