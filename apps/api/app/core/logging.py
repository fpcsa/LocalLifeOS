from __future__ import annotations

import logging
import re

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(password|passphrase|secret|token|note[_ -]?content|markdown|payee|"
    r"transaction[_ -]?description)(\s*[:=]\s*)([^\s,;]+)"
)
_QUERY_STRING = re.compile(r"((?:GET|POST|PUT|PATCH|DELETE|OPTIONS)\s+[^\s?]+)\?[^\s]+")
_record_factory_installed = False
_original_record_factory = logging.getLogRecordFactory()


def redact_log_text(value: str) -> str:
    value = _QUERY_STRING.sub(r"\1?[REDACTED]", value)
    return _SENSITIVE_ASSIGNMENT.sub(r"\1\2[REDACTED]", value)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_log_text(record.getMessage())
        record.args = ()
        return True


def configure_safe_logging() -> None:
    global _record_factory_installed
    if not _record_factory_installed:

        def redacting_factory(*args: object, **kwargs: object) -> logging.LogRecord:
            record = _original_record_factory(*args, **kwargs)
            record.msg = redact_log_text(record.getMessage())
            record.args = ()
            return record

        logging.setLogRecordFactory(redacting_factory)
        _record_factory_installed = True
    for logger_name in ("", "app", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(item, RedactingFilter) for item in logger.filters):
            logger.addFilter(RedactingFilter())
