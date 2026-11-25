"""Terminal-independent progress and cooperative cancellation contracts."""

import math
import threading
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    fraction: float
    message: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(self.fraction) or not 0 <= self.fraction <= 1:
            raise ValueError("progress fraction must be in [0, 1]")


class Progress(Protocol):
    def __call__(self, event: ProgressEvent, /) -> None: ...


class Cancelled(RuntimeError):
    """The operation was cancelled at a cooperative checkpoint."""


class EventFlag(Protocol):
    def set(self) -> None: ...
    def is_set(self) -> bool: ...


class CancelToken:
    """Thread-safe token; a process-shared event can back worker tokens."""

    def __init__(self, event: EventFlag | None = None) -> None:
        self._event = event if event is not None else threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise Cancelled("operation cancelled")


def checkpoint(
    progress: Progress | None,
    cancel: CancelToken | None,
    stage: str,
    fraction: float,
    message: str = "",
) -> None:
    if cancel is not None:
        cancel.raise_if_cancelled()
    if progress is not None:
        progress(ProgressEvent(stage, fraction, message))
    if cancel is not None:
        cancel.raise_if_cancelled()
