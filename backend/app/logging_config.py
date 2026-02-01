import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


def setup_logging(log_dir: str) -> None:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    json_formatter = JSONFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    root_logger.handlers.clear()

    api_handler = logging.handlers.RotatingFileHandler(
        log_path / "api.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    api_handler.setLevel(logging.INFO)
    api_handler.setFormatter(json_formatter)
    api_handler.addFilter(lambda record: record.name.startswith(("app", "uvicorn")))

    worker_handler = logging.handlers.RotatingFileHandler(
        log_path / "worker.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    worker_handler.setLevel(logging.INFO)
    worker_handler.setFormatter(json_formatter)
    worker_handler.addFilter(lambda record: record.name.startswith("worker"))

    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)

    root_logger.addHandler(api_handler)
    root_logger.addHandler(worker_handler)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
