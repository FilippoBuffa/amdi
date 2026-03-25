"""
Log eventi thread-safe in memoria, consumabile dall'API Flask.

Mantiene gli ultimi N eventi come ring-buffer.
Supporta filtro per categoria e long-polling leggero.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class LogEvent:
    ts:       float   = field(default_factory=time.time)
    level:    str     = "INFO"      # INFO | WARNING | ERROR
    worker:   str     = "system"
    message:  str     = ""
    data:     Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.localtime(self.ts)
        ) + f".{int((self.ts % 1) * 1000):03d}"
        return d


class EventLog:
    """
    Ring-buffer thread-safe di LogEvent.
    Espone metodi per pubblicare eventi e leggerli dall'HMI.
    """

    def __init__(self, max_events: int = 500) -> None:
        self._buf:  deque[LogEvent] = deque(maxlen=max_events)
        self._lock  = threading.Lock()
        self._new   = threading.Event()   # segnala nuovi eventi (per polling)

    # -----------------------------------------------------------------------
    # Scrittura
    # -----------------------------------------------------------------------

    def info(self, worker: str, message: str, data: Optional[dict] = None) -> None:
        self._push(LogEvent(level="INFO", worker=worker, message=message, data=data))

    def warning(self, worker: str, message: str, data: Optional[dict] = None) -> None:
        self._push(LogEvent(level="WARNING", worker=worker, message=message, data=data))

    def error(self, worker: str, message: str, data: Optional[dict] = None) -> None:
        self._push(LogEvent(level="ERROR", worker=worker, message=message, data=data))

    def _push(self, event: LogEvent) -> None:
        with self._lock:
            self._buf.append(event)
        self._new.set()
        self._new.clear()

    # -----------------------------------------------------------------------
    # Lettura
    # -----------------------------------------------------------------------

    def get_recent(self, n: int = 50, worker: Optional[str] = None) -> List[dict]:
        """Ritorna gli ultimi n eventi, opzionalmente filtrati per worker."""
        with self._lock:
            events = list(self._buf)

        if worker:
            events = [e for e in events if e.worker == worker]

        return [e.to_dict() for e in events[-n:]]

    def wait_for_new(self, timeout: float = 5.0) -> bool:
        """Blocca finché non arriva un nuovo evento. Ritorna True se è arrivato."""
        return self._new.wait(timeout=timeout)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


# Istanza globale condivisa
event_log = EventLog()
