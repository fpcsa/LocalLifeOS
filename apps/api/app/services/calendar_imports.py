# mypy: disable-error-code="no-untyped-call,no-any-return"
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import UploadFile
from icalendar import Calendar, Component, Event, Timezone, vRecur
from sqlmodel import Session, col, select

from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    AutomationTriggerType,
    CalendarEvent,
    CalendarEventStatus,
    DomainEntityType,
    ImportBatch,
    ImportBatchStatus,
    ImportKind,
    ImportRow,
    ImportRowStatus,
)
from app.models.common import utc_now
from app.repositories.calendar import CalendarEventRepository
from app.repositories.imports import ImportBatchRepository, ImportRowRepository
from app.schemas.imports import ImportApplyRequest, ImportBatchResponse, ImportPreviewResponse
from app.services.automation import dispatch_automation_event
from app.services.events import emit_timeline_event
from app.services.import_files import read_import_upload, store_import_file
from app.services.imports import batch_response, preview_response
from app.services.workspace import get_current_workspace, get_preferences
from app.utils.recurrence import canonicalize_rrule


def _text(component: Component, key: str) -> str | None:
    value = component.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _timezone_name(component: Component, key: str, value: datetime, fallback: str) -> str:
    property_value = component.get(key)
    tzid = str(property_value.params.get("TZID", "")).strip() if property_value else ""
    if tzid:
        try:
            ZoneInfo(tzid)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError(f"{key} uses unknown timezone {tzid}") from exc
        return tzid
    zone_key = getattr(value.tzinfo, "key", None)
    if zone_key:
        return str(zone_key)
    return "UTC" if value.utcoffset() == timedelta(0) else fallback


def _aware(value: datetime, timezone: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=ZoneInfo(timezone))
    return value


def _normalized_event(component: Component, fallback_timezone: str) -> dict[str, Any]:
    uid = _text(component, "UID")
    title = _text(component, "SUMMARY")
    if not title:
        raise ValueError("VEVENT requires SUMMARY")
    start_value = component.decoded("DTSTART")
    if not isinstance(start_value, (date, datetime)):
        raise ValueError("VEVENT requires DTSTART")
    end_property = component.get("DTEND")
    if end_property is not None:
        end_value = component.decoded("DTEND")
    elif component.get("DURATION") is not None:
        end_value = start_value + component.decoded("DURATION")
    else:
        raise ValueError("VEVENT requires DTEND or DURATION")

    result: dict[str, Any] = {
        "title": title,
        "description_markdown": _text(component, "DESCRIPTION"),
        "location": _text(component, "LOCATION"),
        "category": _text(component, "CATEGORIES"),
        "external_uid": uid,
        "source_sequence": int(component.get("SEQUENCE", 0)),
        "preparation_buffer_minutes": 0,
        "travel_buffer_minutes": 0,
        "recovery_buffer_minutes": 0,
    }
    source_status = (_text(component, "STATUS") or "CONFIRMED").upper()
    result["status"] = {
        "TENTATIVE": CalendarEventStatus.TENTATIVE.value,
        "CANCELLED": CalendarEventStatus.CANCELLED.value,
    }.get(source_status, CalendarEventStatus.CONFIRMED.value)

    if isinstance(start_value, datetime):
        if not isinstance(end_value, datetime):
            raise ValueError("timed DTSTART and DTEND must have matching value types")
        timezone = _timezone_name(component, "DTSTART", start_value, fallback_timezone)
        start = _aware(start_value, timezone)
        end = _aware(end_value, timezone)
        if end <= start:
            raise ValueError("DTEND must be after DTSTART")
        result.update(
            {
                "all_day": False,
                "starts_at": start.astimezone(UTC).isoformat(),
                "ends_at": end.astimezone(UTC).isoformat(),
                "all_day_start": None,
                "all_day_end": None,
                "timezone": timezone,
            }
        )
    else:
        if isinstance(end_value, datetime) or not isinstance(end_value, date):
            raise ValueError("all-day DTSTART and DTEND must have matching value types")
        if end_value <= start_value:
            raise ValueError("DTEND must be after DTSTART")
        result.update(
            {
                "all_day": True,
                "starts_at": None,
                "ends_at": None,
                "all_day_start": start_value.isoformat(),
                "all_day_end": end_value.isoformat(),
                "timezone": fallback_timezone,
            }
        )

    recurrence = component.get("RRULE")
    result["recurrence_rrule"] = (
        canonicalize_rrule(recurrence.to_ical().decode("utf-8")) if recurrence else None
    )
    fingerprint_payload = {key: value for key, value in result.items() if key != "external_uid"}
    result["import_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if not result["external_uid"]:
        result["external_uid"] = f"urn:locallife:import:{result['import_fingerprint']}"
    return result


def _issue(code: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "field": field}


def _existing_event(session: Session, workspace_id: UUID, uid: str) -> CalendarEvent | None:
    return session.exec(
        select(CalendarEvent).where(
            col(CalendarEvent.workspace_id) == workspace_id,
            col(CalendarEvent.deleted_at).is_(None),
            col(CalendarEvent.external_uid) == uid,
        )
    ).first()


def preview_calendar_import(session: Session, upload: UploadFile) -> ImportPreviewResponse:
    workspace = get_current_workspace(session)
    preferences = get_preferences(session)
    data, filename, source_fingerprint = read_import_upload(upload, extension=".ics")
    repository = ImportBatchRepository(session)
    existing_batch = repository.find_source(
        workspace.id, ImportKind.CALENDAR_ICS, source_fingerprint
    )
    if existing_batch is not None:
        return preview_response(session, existing_batch)

    try:
        calendar = Calendar.from_ical(data)
        components = list(calendar.walk("VEVENT"))
    except Exception as exc:
        raise DomainValidationError(
            "invalid_ics", "The calendar file could not be parsed."
        ) from exc
    if not components:
        raise DomainValidationError("empty_calendar", "The calendar contains no events.")

    batch = ImportBatch(
        workspace_id=workspace.id,
        kind=ImportKind.CALENDAR_ICS,
        status=ImportBatchStatus.PREVIEWED,
        original_filename=filename,
        stored_path="pending",
        source_fingerprint=source_fingerprint,
        total_rows=len(components),
        summary={"calendar_name": str(calendar.get("X-WR-CALNAME", "Imported calendar"))},
    )
    batch.stored_path = store_import_file(batch.id, filename, data)
    rows: list[ImportRow] = []
    for index, component in enumerate(components, start=1):
        raw = {
            "uid": _text(component, "UID"),
            "summary": _text(component, "SUMMARY"),
        }
        try:
            normalized = _normalized_event(component, preferences.timezone)
            current = _existing_event(session, workspace.id, str(normalized["external_uid"]))
            if current is None:
                status = ImportRowStatus.NEW
                included = True
                duplicate_kind = None
                duplicate_target_id = None
            elif current.import_fingerprint == normalized["import_fingerprint"]:
                status = ImportRowStatus.DUPLICATE
                included = False
                duplicate_kind = "exact"
                duplicate_target_id = current.id
            else:
                status = ImportRowStatus.CHANGED
                included = True
                duplicate_kind = None
                duplicate_target_id = current.id
                normalized["expected_revision"] = current.revision
            row = ImportRow(
                workspace_id=workspace.id,
                batch_id=batch.id,
                row_number=index,
                status=status,
                included=included,
                fingerprint=str(normalized["import_fingerprint"]),
                raw_data=raw,
                normalized_data=normalized,
                issues=[],
                duplicate_kind=duplicate_kind,
                duplicate_target_id=duplicate_target_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            row = ImportRow(
                workspace_id=workspace.id,
                batch_id=batch.id,
                row_number=index,
                status=ImportRowStatus.INVALID,
                included=False,
                raw_data=raw,
                normalized_data={},
                issues=[_issue("invalid_event", str(exc))],
            )
        rows.append(row)

    batch.new_count = sum(row.status == ImportRowStatus.NEW for row in rows)
    batch.changed_count = sum(row.status == ImportRowStatus.CHANGED for row in rows)
    batch.duplicate_count = sum(row.status == ImportRowStatus.DUPLICATE for row in rows)
    batch.invalid_count = sum(row.status == ImportRowStatus.INVALID for row in rows)
    with transaction(session):
        repository.add(batch)
        row_repository = ImportRowRepository(session)
        for row in rows:
            row_repository.add(row)
    return preview_response(session, batch)


def _event_values(normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": normalized["title"],
        "description_markdown": normalized.get("description_markdown"),
        "location": normalized.get("location"),
        "status": CalendarEventStatus(normalized["status"]),
        "all_day": normalized["all_day"],
        "starts_at": (
            datetime.fromisoformat(normalized["starts_at"]) if normalized.get("starts_at") else None
        ),
        "ends_at": (
            datetime.fromisoformat(normalized["ends_at"]) if normalized.get("ends_at") else None
        ),
        "all_day_start": (
            date.fromisoformat(normalized["all_day_start"])
            if normalized.get("all_day_start")
            else None
        ),
        "all_day_end": (
            date.fromisoformat(normalized["all_day_end"]) if normalized.get("all_day_end") else None
        ),
        "timezone": normalized["timezone"],
        "recurrence_rrule": normalized.get("recurrence_rrule"),
        "category": normalized.get("category"),
        "preparation_buffer_minutes": normalized.get("preparation_buffer_minutes", 0),
        "travel_buffer_minutes": normalized.get("travel_buffer_minutes", 0),
        "recovery_buffer_minutes": normalized.get("recovery_buffer_minutes", 0),
        "external_uid": normalized["external_uid"],
        "source_sequence": normalized.get("source_sequence", 0),
        "import_fingerprint": normalized["import_fingerprint"],
    }


def apply_calendar_import(
    session: Session, batch_id: UUID, request: ImportApplyRequest
) -> ImportBatchResponse:
    workspace = get_current_workspace(session)
    batch_repository = ImportBatchRepository(session)
    batch = batch_repository.get_workspace(workspace.id, batch_id)
    if batch is None or batch.kind != ImportKind.CALENDAR_ICS:
        raise DomainNotFoundError("calendar import batch", batch_id)
    if batch.applied_at is not None:
        return batch_response(batch)
    rows = ImportRowRepository(session).list_batch(workspace.id, batch.id)
    selected = set(request.included_row_ids) if request.included_row_ids is not None else None
    event_repository = CalendarEventRepository(session)
    imported = 0
    created_events: list[CalendarEvent] = []
    with transaction(session):
        for row in rows:
            include = row.included if selected is None else row.id in selected
            if not include or row.status not in {ImportRowStatus.NEW, ImportRowStatus.CHANGED}:
                if row.status in {ImportRowStatus.NEW, ImportRowStatus.CHANGED}:
                    row.status = ImportRowStatus.EXCLUDED
                    row.revision += 1
                    session.add(row)
                continue
            values = _event_values(row.normalized_data)
            current = _existing_event(session, workspace.id, values["external_uid"])
            if row.status == ImportRowStatus.NEW:
                if current is not None:
                    raise DomainConflictError(
                        "calendar_import_stale", "A new event with this calendar UID now exists."
                    )
                event = event_repository.add(CalendarEvent(workspace_id=workspace.id, **values))
                action = "calendar_event_imported"
                created_events.append(event)
            else:
                expected_revision = int(row.normalized_data["expected_revision"])
                if current is None or current.revision != expected_revision:
                    raise DomainConflictError(
                        "calendar_import_stale",
                        "A changed calendar event was edited after preview.",
                        {"row_id": str(row.id)},
                    )
                event = event_repository.update(workspace.id, current.id, expected_revision, values)
                action = "calendar_event_import_updated"
            row.status = ImportRowStatus.IMPORTED
            row.target_id = event.id
            row.revision += 1
            session.add(row)
            imported += 1
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.CALENDAR_EVENT,
                entity_id=event.id,
                action=action,
                title=f"Calendar import: {event.title}",
                payload={"import_batch_id": str(batch.id)},
            )
        batch.status = ImportBatchStatus.APPLIED
        batch.imported_count = imported
        batch.applied_at = utc_now()
        batch.revision += 1
        session.add(batch)
    for event in created_events:
        dispatch_automation_event(
            session,
            AutomationTriggerType.EVENT_CREATED,
            context={
                "entity_type": DomainEntityType.CALENDAR_EVENT.value,
                "entity_id": str(event.id),
                "title": event.title,
                "category": event.category,
                "location": event.location,
                "status": event.status.value,
                "timezone": event.timezone,
            },
            source_key=f"calendar-event:{event.id}",
        )
    return batch_response(batch)


def export_calendar_events(session: Session, event_ids: list[UUID] | None) -> bytes:
    workspace = get_current_workspace(session)
    query = select(CalendarEvent).where(
        col(CalendarEvent.workspace_id) == workspace.id,
        col(CalendarEvent.deleted_at).is_(None),
    )
    if event_ids is not None:
        if not event_ids:
            raise DomainValidationError("empty_calendar_export", "Select at least one event.")
        query = query.where(col(CalendarEvent.id).in_(event_ids))
    events = list(
        session.exec(query.order_by(col(CalendarEvent.starts_at), col(CalendarEvent.id))).all()
    )
    if event_ids is not None and len(events) != len(set(event_ids)):
        raise DomainNotFoundError("calendar event", "selection")
    calendar = Calendar()
    calendar.add("prodid", "-//LocalLife OS//Local calendar export//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    added_timezones: set[str] = set()
    for item in events:
        component = Event()
        component.add("uid", item.external_uid or f"locallife-{item.id}@local")
        component.add("summary", item.title)
        component.add("dtstamp", item.updated_at.astimezone(UTC))
        if item.description_markdown:
            component.add("description", item.description_markdown)
        if item.location:
            component.add("location", item.location)
        if item.category:
            component.add("categories", item.category)
        component.add("status", item.status.value.upper())
        component.add("sequence", item.source_sequence)
        if item.all_day:
            component.add("dtstart", item.all_day_start)
            component.add("dtend", item.all_day_end)
        else:
            if item.starts_at is None or item.ends_at is None:
                raise DomainValidationError(
                    "invalid_calendar_event",
                    "A timed event is missing its start or end timestamp.",
                )
            zone = ZoneInfo(item.timezone)
            component.add("dtstart", item.starts_at.astimezone(zone))
            component.add("dtend", item.ends_at.astimezone(zone))
            if item.timezone != "UTC" and item.timezone not in added_timezones:
                calendar.add_component(Timezone.from_tzinfo(zone))
                added_timezones.add(item.timezone)
        if item.recurrence_rrule:
            component.add("rrule", vRecur.from_ical(item.recurrence_rrule))
        component.add("x-locallife-preparation-minutes", item.preparation_buffer_minutes)
        component.add("x-locallife-travel-minutes", item.travel_buffer_minutes)
        component.add("x-locallife-recovery-minutes", item.recovery_buffer_minutes)
        calendar.add_component(component)
    return calendar.to_ical()
