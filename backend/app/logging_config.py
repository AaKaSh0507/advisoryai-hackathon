import json
import logging
import logging.handlers
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Context variables for correlation tracking
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)
document_id_var: ContextVar[str | None] = ContextVar("document_id", default=None)
template_id_var: ContextVar[str | None] = ContextVar("template_id", default=None)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return f"corr-{uuid.uuid4().hex[:12]}"


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set correlation ID for current context. Generates one if not provided."""
    cid = correlation_id or generate_correlation_id()
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> str | None:
    """Get correlation ID from current context."""
    return correlation_id_var.get()


def set_job_context(
    job_id: str | None = None, document_id: str | None = None, template_id: str | None = None
):
    """Set job-related context for logging."""
    if job_id:
        job_id_var.set(job_id)
    if document_id:
        document_id_var.set(document_id)
    if template_id:
        template_id_var.set(template_id)


def clear_context():
    """Clear all context variables."""
    correlation_id_var.set(None)
    job_id_var.set(None)
    document_id_var.set(None)
    template_id_var.set(None)


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter with correlation ID and context support.

    Produces logs with:
    - timestamp (ISO 8601)
    - level
    - logger name
    - message
    - correlation_id (if set)
    - job_id (if set)
    - document_id (if set)
    - template_id (if set)
    - module, function, line
    - exception (if present)
    - extra data (if provided)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation context
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        job_id = job_id_var.get()
        if job_id:
            log_data["job_id"] = job_id

        document_id = document_id_var.get()
        if document_id:
            log_data["document_id"] = document_id

        template_id = template_id_var.get()
        if template_id:
            log_data["template_id"] = template_id

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra data if present
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["extra"] = record.extra_data

        # Add any custom attributes passed to the log call
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "extra_data",
            "message",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                try:
                    json.dumps(value)  # Check if serializable
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with color support."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)

        # Build context string
        context_parts = []
        correlation_id = correlation_id_var.get()
        if correlation_id:
            context_parts.append(f"cid={correlation_id}")
        job_id = job_id_var.get()
        if job_id:
            context_parts.append(f"job={job_id[:8]}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        formatted = (
            f"{color}{timestamp} {record.levelname:8}{self.RESET} "
            f"{record.name}{context_str} - {record.getMessage()}"
        )

        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def setup_logging(log_dir: str, enable_console: bool = True) -> None:
    """
    Set up structured logging with file and optional console output.

    Creates separate log files for:
    - api.log: API and application logs
    - worker.log: Worker process logs
    - errors.log: All error-level logs
    - jobs.log: Job-specific logs
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    json_formatter = StructuredJSONFormatter()
    console_formatter = ConsoleFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    # API log handler
    api_handler = logging.handlers.RotatingFileHandler(
        log_path / "api.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    api_handler.setLevel(logging.INFO)
    api_handler.setFormatter(json_formatter)
    api_handler.addFilter(lambda record: record.name.startswith(("app", "uvicorn")))

    # Worker log handler
    worker_handler = logging.handlers.RotatingFileHandler(
        log_path / "worker.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    worker_handler.setLevel(logging.INFO)
    worker_handler.setFormatter(json_formatter)
    worker_handler.addFilter(lambda record: record.name.startswith("worker"))

    # Error log handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)

    # Jobs log handler
    jobs_handler = logging.handlers.RotatingFileHandler(
        log_path / "jobs.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    jobs_handler.setLevel(logging.INFO)
    jobs_handler.setFormatter(json_formatter)
    jobs_handler.addFilter(lambda record: "job" in record.name.lower())

    root_logger.addHandler(api_handler)
    root_logger.addHandler(worker_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(jobs_handler)

    # Console handler (for development)
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


class LogContext:
    """
    Context manager for setting logging context.

    Usage:
        with LogContext(correlation_id="abc", job_id="123"):
            logger.info("This log will have correlation_id and job_id")
    """

    def __init__(
        self,
        correlation_id: str | None = None,
        job_id: str | None = None,
        document_id: str | None = None,
        template_id: str | None = None,
        auto_generate_correlation_id: bool = False,
    ):
        self.correlation_id = correlation_id
        self.job_id = job_id
        self.document_id = document_id
        self.template_id = template_id
        self.auto_generate_correlation_id = auto_generate_correlation_id

        # Store previous values for restoration
        self._prev_correlation_id: str | None = None
        self._prev_job_id: str | None = None
        self._prev_document_id: str | None = None
        self._prev_template_id: str | None = None

    def __enter__(self):
        # Store previous values
        self._prev_correlation_id = correlation_id_var.get()
        self._prev_job_id = job_id_var.get()
        self._prev_document_id = document_id_var.get()
        self._prev_template_id = template_id_var.get()

        # Set new values
        if self.correlation_id:
            correlation_id_var.set(self.correlation_id)
        elif self.auto_generate_correlation_id and not self._prev_correlation_id:
            correlation_id_var.set(generate_correlation_id())

        if self.job_id:
            job_id_var.set(self.job_id)
        if self.document_id:
            document_id_var.set(self.document_id)
        if self.template_id:
            template_id_var.set(self.template_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous values
        correlation_id_var.set(self._prev_correlation_id)
        job_id_var.set(self._prev_job_id)
        document_id_var.set(self._prev_document_id)
        template_id_var.set(self._prev_template_id)
        return False
