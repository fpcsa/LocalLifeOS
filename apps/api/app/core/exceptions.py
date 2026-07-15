from __future__ import annotations

from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class DomainNotFoundError(DomainError):
    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(
            code="not_found",
            message=f"{resource} was not found.",
            status_code=404,
            details={"resource": resource, "identifier": str(identifier)},
        )


class DomainConflictError(DomainError):
    def __init__(self, code: str, message: str, details: Any | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details=details,
        )


class RevisionConflictError(DomainConflictError):
    def __init__(self, resource: str, expected: int, current: int) -> None:
        super().__init__(
            code="revision_conflict",
            message=f"{resource} changed since it was read.",
            details={"expected_revision": expected, "current_revision": current},
        )


class DomainValidationError(DomainError):
    def __init__(self, code: str, message: str, details: Any | None = None) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=422,
            details=details,
        )
