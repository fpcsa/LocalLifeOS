from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import DomainValidationError
from app.services.storage_lock import STORAGE_LOCK

SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def read_import_upload(upload: UploadFile, *, extension: str) -> tuple[bytes, str, str]:
    settings = get_settings()
    filename = (upload.filename or "").strip()
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise DomainValidationError("invalid_import_filename", "Choose a simple local filename.")
    if Path(filename).suffix.casefold() != extension.casefold():
        raise DomainValidationError(
            "invalid_import_type", f"The selected file must use the {extension} extension."
        )
    data = upload.file.read(settings.max_import_bytes + 1)
    if len(data) > settings.max_import_bytes:
        raise DomainValidationError(
            "import_too_large",
            f"Import files cannot exceed {settings.max_import_bytes} bytes.",
        )
    if not data:
        raise DomainValidationError("empty_import", "The selected import file is empty.")
    return data, filename, hashlib.sha256(data).hexdigest()


def store_import_file(batch_id: UUID, filename: str, data: bytes) -> str:
    imports_root = get_settings().imports_dir
    if imports_root is None:
        raise RuntimeError("imports directory is not configured")
    safe_name = SAFE_NAME.sub("_", filename).strip(" .") or "import.bin"
    relative = Path(str(batch_id)) / safe_name
    target = (imports_root / relative).resolve()
    if not target.is_relative_to(imports_root.resolve()):
        raise DomainValidationError("unsafe_import_path", "Import storage path is unsafe.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with STORAGE_LOCK, target.open("xb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    return relative.as_posix()


def sanitize_spreadsheet_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text
