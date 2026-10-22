"""Logs estruturados (JSON, prontos para o Cloud Logging) com segredos mascarados."""

from __future__ import annotations

import json
import logging
import re
import sys

_SECRET = re.compile(r"(bot\d+:[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{10,}|mongodb(\+srv)?://[^\s\"']+|(?i:token|secret|password)=[^&\s]+)")


def redact(text: str) -> str:
    return _SECRET.sub("[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"severity": record.levelname, "logger": record.name, "message": redact(record.getMessage()),
                   "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")}
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)
