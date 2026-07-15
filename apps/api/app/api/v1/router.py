from fastapi import APIRouter

from app.api.v1.routes import (
    attachments,
    calendar,
    commitments,
    finance_accounts,
    finance_budgets,
    finance_planning,
    finance_reports,
    finance_subscriptions,
    finance_transactions,
    goals,
    health,
    meta,
    notes,
    projects,
    scenarios,
    scheduling,
    system,
    tags,
    tasks,
    timeline,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(workspaces.router)
api_router.include_router(tags.router)
api_router.include_router(timeline.router)
api_router.include_router(meta.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(notes.router)
api_router.include_router(attachments.router)
api_router.include_router(calendar.router)
api_router.include_router(commitments.router)
api_router.include_router(scheduling.router)
api_router.include_router(scenarios.router)
api_router.include_router(finance_accounts.router)
api_router.include_router(finance_transactions.router)
api_router.include_router(finance_planning.router)
api_router.include_router(finance_budgets.router)
api_router.include_router(finance_subscriptions.router)
api_router.include_router(finance_reports.router)
api_router.include_router(goals.router)
