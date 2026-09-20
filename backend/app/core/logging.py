"""Structured JSON logging for SentinelCrypt AI."""
import logging
import sys

_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=_FORMAT,
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
