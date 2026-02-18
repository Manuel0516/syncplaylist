from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from googleapiclient.errors import HttpError
from spotipy import SpotifyException


T = TypeVar("T")


def run_with_retries(
    operation: Callable[[], T],
    *,
    description: str,
    retries: int = 4,
    base_delay_seconds: float = 1.0,
    logger: logging.Logger | None = None,
) -> T:
    """Run an operation with bounded retries and exponential backoff."""

    log = logger or logging.getLogger(__name__)
    attempt = 1
    while True:
        try:
            return operation()
        except (SpotifyException, HttpError, TimeoutError, ConnectionError) as exc:
            if attempt >= retries:
                raise

            retry_after = _extract_retry_after_seconds(exc)
            sleep_seconds = retry_after if retry_after is not None else base_delay_seconds * (2 ** (attempt - 1))
            log.warning(
                "%s failed on attempt %s/%s (%s). Retrying in %.1fs",
                description,
                attempt,
                retries,
                exc,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
            attempt += 1


def _extract_retry_after_seconds(exc: Exception) -> float | None:
    if isinstance(exc, SpotifyException):
        header = None
        if exc.headers:
            header = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
        if header:
            try:
                return float(header)
            except ValueError:
                return None

    if isinstance(exc, HttpError):
        retry_after = exc.resp.get("retry-after") if exc.resp else None
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                return None

    return None
