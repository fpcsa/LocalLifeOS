from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, col, select

from app.models import (
    CategoryKind,
    SystemSetting,
    TransactionCategory,
    UserPreferences,
    Workspace,
)

DEFAULT_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_PREFERENCES_ID = UUID("00000000-0000-4000-8000-000000000002")
DEFAULT_CATEGORIES = (
    (UUID("00000000-0000-4000-8000-000000000010"), "Salary", CategoryKind.INCOME),
    (UUID("00000000-0000-4000-8000-000000000011"), "Other income", CategoryKind.INCOME),
    (UUID("00000000-0000-4000-8000-000000000012"), "Housing", CategoryKind.EXPENSE),
    (UUID("00000000-0000-4000-8000-000000000013"), "Food", CategoryKind.EXPENSE),
    (UUID("00000000-0000-4000-8000-000000000014"), "Transport", CategoryKind.EXPENSE),
    (UUID("00000000-0000-4000-8000-000000000015"), "Utilities", CategoryKind.EXPENSE),
    (UUID("00000000-0000-4000-8000-000000000016"), "Other expense", CategoryKind.EXPENSE),
)


def seed_default_data(session: Session, *, timezone: str, currency_code: str = "EUR") -> None:
    workspace = session.exec(
        select(Workspace).where(
            col(Workspace.is_default).is_(True),
            col(Workspace.deleted_at).is_(None),
        )
    ).first()
    if workspace is None:
        workspace = Workspace(
            id=DEFAULT_WORKSPACE_ID,
            name="Local workspace",
            description="Private workspace stored on this device.",
            is_default=True,
        )
        session.add(workspace)
        session.flush()

    preferences = session.exec(
        select(UserPreferences).where(col(UserPreferences.workspace_id) == workspace.id)
    ).first()
    if preferences is None:
        session.add(
            UserPreferences(
                id=DEFAULT_PREFERENCES_ID,
                workspace_id=workspace.id,
                timezone=timezone,
                locale="en",
                currency_code=currency_code,
            )
        )

    timezone_setting = session.exec(
        select(SystemSetting).where(col(SystemSetting.key) == "user.timezone")
    ).first()
    if timezone_setting is None:
        session.add(
            SystemSetting(
                key="user.timezone",
                value=timezone,
                description="IANA timezone used to present UTC timestamps locally.",
            )
        )

    existing_categories = {
        name
        for name in session.exec(
            select(TransactionCategory.name).where(
                col(TransactionCategory.workspace_id) == workspace.id,
                col(TransactionCategory.deleted_at).is_(None),
            )
        ).all()
    }
    for category_id, name, kind in DEFAULT_CATEGORIES:
        if name not in existing_categories:
            session.add(
                TransactionCategory(
                    id=category_id,
                    workspace_id=workspace.id,
                    name=name,
                    kind=kind,
                    is_default=True,
                )
            )

    session.flush()
