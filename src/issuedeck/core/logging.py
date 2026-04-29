"""Root logger configuration."""

from __future__ import annotations

import logging
import os
import sys


def configure_logging(level: str = "info") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    if os.environ.get("ISSUEDECK_LOG_JSON") == "1":
        fmt = '{"ts":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt, stream=sys.stderr,
    )
