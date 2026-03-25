"""
Modello per le statistiche di produzione.
Tiene contatori in memoria (aggiornati in real-time) e supporta
la serializzazione per il DB e per l'HMI.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Optional
from collections import deque


@dataclass
class ShiftStats:
    """Statistiche per un singolo turno / sessione."""

    # --- Timestamp ---
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    # --- Contatori pezzi ---
    total_pieces: int = 0
    ok_pieces: int = 0
    ng_pieces: int = 0
    timeout_pieces: int = 0
    error_pieces: int = 0

    # --- Contatori batch ---
    total_batches: int = 0
    full_ok_batches: int = 0    # batch in cui tutti i 4 pezzi sono OK

    # --- Lock per accesso thread-safe ---
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # -----------------------------------------------------------------------
    # Aggiornamento
    # -----------------------------------------------------------------------

    def record_piece_ok(self) -> None:
        with self._lock:
            self.total_pieces += 1
            self.ok_pieces += 1

    def record_piece_ng(self) -> None:
        with self._lock:
            self.total_pieces += 1
            self.ng_pieces += 1

    def record_piece_timeout(self) -> None:
        with self._lock:
            self.total_pieces += 1
            self.timeout_pieces += 1

    def record_piece_error(self) -> None:
        with self._lock:
            self.total_pieces += 1
            self.error_pieces += 1

    def record_batch(self, all_ok: bool) -> None:
        with self._lock:
            self.total_batches += 1
            if all_ok:
                self.full_ok_batches += 1

    # -----------------------------------------------------------------------
    # Proprietà derivate
    # -----------------------------------------------------------------------

    @property
    def ng_rate(self) -> float:
        """Percentuale NG su pezzi ispezionati (0.0 – 1.0)."""
        inspected = self.ok_pieces + self.ng_pieces
        return self.ng_pieces / inspected if inspected > 0 else 0.0

    @property
    def ok_rate(self) -> float:
        return 1.0 - self.ng_rate

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()

    @property
    def throughput_per_hour(self) -> float:
        """Pezzi ispezionati per ora."""
        elapsed_h = self.elapsed_seconds / 3600
        inspected = self.ok_pieces + self.ng_pieces
        return inspected / elapsed_h if elapsed_h > 0 else 0.0

    # -----------------------------------------------------------------------
    # Serializzazione
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "elapsed_seconds": round(self.elapsed_seconds, 1),
                "pieces": {
                    "total": self.total_pieces,
                    "ok": self.ok_pieces,
                    "ng": self.ng_pieces,
                    "timeout": self.timeout_pieces,
                    "error": self.error_pieces,
                },
                "rates": {
                    "ok_rate": round(self.ok_rate * 100, 2),
                    "ng_rate": round(self.ng_rate * 100, 2),
                    "throughput_per_hour": round(self.throughput_per_hour, 1),
                },
                "batches": {
                    "total": self.total_batches,
                    "full_ok": self.full_ok_batches,
                },
            }


class StatsManager:
    """
    Gestisce le statistiche della sessione corrente e mantiene
    un ring-buffer degli ultimi N risultati per i grafici trend.
    """

    def __init__(self, trend_window: int = 100) -> None:
        self.current: ShiftStats = ShiftStats()
        # Ring buffer: ogni entry è {"ts": iso, "result": "OK"|"NG"}
        self._trend: Deque[dict] = deque(maxlen=trend_window)
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Avvia una nuova sessione/turno."""
        with self._lock:
            self.current = ShiftStats()
            self._trend.clear()

    def record_ok(self) -> None:
        self.current.record_piece_ok()
        with self._lock:
            self._trend.append({"ts": datetime.utcnow().isoformat(), "result": "OK"})

    def record_ng(self) -> None:
        self.current.record_piece_ng()
        with self._lock:
            self._trend.append({"ts": datetime.utcnow().isoformat(), "result": "NG"})

    def record_timeout(self) -> None:
        self.current.record_piece_timeout()

    def record_error(self) -> None:
        self.current.record_piece_error()

    def record_batch(self, all_ok: bool) -> None:
        self.current.record_batch(all_ok)

    def get_trend(self) -> list:
        with self._lock:
            return list(self._trend)

    def to_dict(self) -> dict:
        return {
            "current_shift": self.current.to_dict(),
            "trend": self.get_trend(),
        }
