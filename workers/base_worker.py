"""
Classe base per i worker thread delle telecamere.

Ogni worker:
1. Apre la camera e segnala al PLC che è pronto
2. Loop: grab() → inferenza → scrivi risultati → alza flag → attendi reset → repeat
3. Gestisce errori con retry ed espone stato all'orchestratore
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class WorkerState(str, Enum):
    IDLE          = "idle"
    INITIALIZING  = "initializing"
    READY         = "ready"
    WAITING       = "waiting"    # in attesa di trigger (grab() bloccante)
    PROCESSING    = "processing" # inferenza in corso
    WRITING       = "writing"    # scrittura PLC
    HANDSHAKE     = "handshake"  # attesa che PLC resetti il flag
    ERROR         = "error"
    STOPPED       = "stopped"


@dataclass
class WorkerStatus:
    state:         WorkerState       = WorkerState.IDLE
    frame_count:   int               = 0
    error_count:   int               = 0
    last_error:    Optional[str]     = None
    last_result:   Optional[dict]    = None    # JSON-serializzabile
    last_frame_ts: Optional[float]   = None
    inference_ms:  float             = 0.0


class BaseWorker(ABC):
    """
    Worker generico per una camera.

    Sottoclassi devono implementare:
        _init_camera()        → apre camera e motore di inferenza
        _ready_var()          → nome variabile PLC "CamReady"
        _process_frame(frame) → inferenza + scrittura PLC
                                restituisce dict con risultato (per log/HMI)
        _handshake_var()      → nome variabile PLC da monitorare per handshake
    """

    MAX_CONSECUTIVE_ERRORS = 5
    RETRY_DELAY_S          = 3.0

    def __init__(self, name: str, plc_client, poll_interval_s: float = 0.05) -> None:
        self.name          = name
        self._plc          = plc_client
        self._poll_s       = poll_interval_s

        self._status       = WorkerStatus()
        self._status_lock  = threading.Lock()
        self._stop_event   = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._consecutive_errors = 0

    # -----------------------------------------------------------------------
    # Ciclo di vita pubblico
    # -----------------------------------------------------------------------

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"worker-{self.name}",
            daemon=True,
        )
        self._thread.start()
        log.info("[%s] thread avviato.", self.name)

    def stop(self) -> None:
        log.info("[%s] stop richiesto.", self.name)
        self._stop_event.set()
        self._on_stop_requested()
        if self._thread:
            self._thread.join(timeout=10.0)
        self._set_state(WorkerState.STOPPED)

    def get_status(self) -> WorkerStatus:
        with self._status_lock:
            return self._status

    # -----------------------------------------------------------------------
    # Loop principale
    # -----------------------------------------------------------------------

    def _run(self) -> None:
        self._set_state(WorkerState.INITIALIZING)
        try:
            self._init_camera()
        except Exception as exc:
            log.error("[%s] errore inizializzazione: %s", self.name, exc)
            self._set_state(WorkerState.ERROR)
            self._record_error(str(exc))
            return

        # Segnala al PLC che questa camera è pronta
        try:
            self._plc.write(self._ready_var(), True, "BOOL")
            log.info("[%s] → PLC: %s = TRUE", self.name, self._ready_var())
        except Exception as exc:
            log.error("[%s] errore scrittura PLC ready: %s", self.name, exc)

        self._set_state(WorkerState.READY)

        while not self._stop_event.is_set():
            try:
                self._cycle()
                self._consecutive_errors = 0
            except StopIteration:
                break
            except Exception as exc:
                self._consecutive_errors += 1
                self._record_error(str(exc))
                log.error("[%s] errore ciclo (%d/%d): %s",
                          self.name, self._consecutive_errors,
                          self.MAX_CONSECUTIVE_ERRORS, exc)

                if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                    log.critical("[%s] troppi errori consecutivi. Stop.", self.name)
                    self._set_state(WorkerState.ERROR)
                    break

                self._stop_event.wait(self.RETRY_DELAY_S)

        self._cleanup()
        self._set_state(WorkerState.STOPPED)
        log.info("[%s] terminato.", self.name)

    def _cycle(self) -> None:
        """Un ciclo completo: grab → inferenza → scrittura → handshake."""
        # 1. Attendi frame (grab blocca fino a trigger PLC)
        self._set_state(WorkerState.WAITING)
        frame = self._grab_frame()

        if self._stop_event.is_set():
            raise StopIteration

        # 2. Inferenza
        self._set_state(WorkerState.PROCESSING)
        result_dict = self._process_frame(frame)

        # 3. Handshake: attendi che il PLC resetti il flag
        self._set_state(WorkerState.HANDSHAKE)
        self._wait_handshake()

        # 4. Aggiorna statistiche
        with self._status_lock:
            self._status.frame_count  += 1
            self._status.last_result   = result_dict
            self._status.last_frame_ts = frame.timestamp

    # -----------------------------------------------------------------------
    # Metodi astratti da implementare nelle sottoclassi
    # -----------------------------------------------------------------------

    @abstractmethod
    def _init_camera(self) -> None:
        """Apre la camera e inizializza il motore di inferenza."""
        ...

    @abstractmethod
    def _ready_var(self) -> str:
        """Nome variabile PLC bXxxCamReady da scrivere TRUE a inizio."""
        ...

    @abstractmethod
    def _process_frame(self, frame) -> dict:
        """
        Esegue inferenza e scrive risultati sul PLC.
        Deve alzare il flag handshake prima di tornare.
        Restituisce dict con i risultati (per log/HMI).
        """
        ...

    @abstractmethod
    def _handshake_var(self) -> str:
        """Nome variabile PLC da monitorare per il reset (handshake)."""
        ...

    @abstractmethod
    def _grab_frame(self):
        """Acquisisce un frame dalla camera (bloccante)."""
        ...

    # -----------------------------------------------------------------------
    # Handshake
    # -----------------------------------------------------------------------

    def _wait_handshake(self) -> None:
        """
        Attende che il PLC abbia letto i dati (resetta la variabile handshake a FALSE).
        Polling con stop event per uscire pulito in caso di shutdown.
        """
        var = self._handshake_var()
        while not self._stop_event.is_set():
            try:
                val = self._plc.read(var, "BOOL")
                if val is False:
                    return
            except Exception as exc:
                log.warning("[%s] errore handshake polling: %s", self.name, exc)
            self._stop_event.wait(self._poll_s)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _set_state(self, state: WorkerState) -> None:
        with self._status_lock:
            self._status.state = state

    def _record_error(self, msg: str) -> None:
        with self._status_lock:
            self._status.error_count += 1
            self._status.last_error   = msg

    def _on_stop_requested(self) -> None:
        """Hook per sottoclassi: es. unblock grab()."""
        pass

    def _cleanup(self) -> None:
        """Hook per sottoclassi: chiudi camera."""
        pass
