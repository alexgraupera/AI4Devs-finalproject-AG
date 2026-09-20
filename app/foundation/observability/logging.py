"""Structured logging: one JSON object per event, so the logs can be counted, not just read.

The dashboard of #4 is built from these events, which is the reason they carry the model, the
tokens, the latency and the cost instead of a sentence describing them.
"""

import logging

import structlog


def configure_logging(level: int = logging.INFO, json_output: bool = True) -> None:
    renderer = structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
