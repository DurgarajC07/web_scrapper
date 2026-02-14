"""
Structured logging with rich console output and file logging.
"""

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

import structlog
from rich.console import Console
from rich.logging import RichHandler


console = Console()


def setup_logger(
    log_level: str = "INFO",
    log_file: str | None = None,
    enable_json: bool = False,
) -> structlog.BoundLogger:
    """Configure structured logging for the entire application."""

    # Standard library logging setup
    handlers: list[logging.Handler] = [
        RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            show_path=False,
        )
    ]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s"
            )
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )

    # Structlog configuration
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("iawic")


def get_logger(name: str = "iawic") -> structlog.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)


# Alias for backward compatibility
setup_logging = setup_logger