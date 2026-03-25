"""
Interfaccia astratta per la comunicazione con il PLC.
Sia il client reale (PyADS) che il mock devono implementare questa classe.
Il resto del codice dipende SOLO da questa interfaccia.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional


class PLCState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED    = "connected"
    ERROR        = "error"


@dataclass
class PLCStatus:
    """Snapshot dello stato PLC letto ad ogni ciclo di polling."""
    state: PLCState = PLCState.DISCONNECTED
    machine_running: bool = False
    machine_error: bool = False
    error_message: Optional[str] = None


@dataclass
class TrackingResult:
    x: float
    y: float
    ok: bool = True


@dataclass
class OrientationResult:
    angle: float
    ok: bool = True


@dataclass
class InspectionResult:
    results: List[bool]   # 4 elementi, True=OK False=NG
    ok: bool = True


# Tipo per le callback dei trigger
TriggerCallback = Callable[[], None]


class BaseADSClient(ABC):
    """
    Interfaccia comune per la comunicazione PLC.

    Pattern d'uso:
        client.on_trigger_tracking(lambda: ...)
        client.on_trigger_orientation(lambda: ...)
        client.on_trigger_inspection(lambda: ...)
        client.start()
        ...
        client.write_tracking_result(TrackingResult(x=10.0, y=20.0))
        ...
        client.stop()
    """

    def __init__(self) -> None:
        self._cb_tracking:    Optional[TriggerCallback] = None
        self._cb_orientation: Optional[TriggerCallback] = None
        self._cb_inspection:  Optional[TriggerCallback] = None
        self._cb_status:      Optional[Callable[[PLCStatus], None]] = None

    # -----------------------------------------------------------------------
    # Registrazione callback
    # -----------------------------------------------------------------------

    def on_trigger_tracking(self, cb: TriggerCallback) -> None:
        """Registra callback chiamata quando il PLC triggera CAM1."""
        self._cb_tracking = cb

    def on_trigger_orientation(self, cb: TriggerCallback) -> None:
        """Registra callback chiamata quando il PLC triggera CAM2."""
        self._cb_orientation = cb

    def on_trigger_inspection(self, cb: TriggerCallback) -> None:
        """Registra callback chiamata quando il PLC triggera CAM3."""
        self._cb_inspection = cb

    def on_status_change(self, cb: Callable[[PLCStatus], None]) -> None:
        """Registra callback chiamata ad ogni cambio di stato PLC."""
        self._cb_status = cb

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    @abstractmethod
    def start(self) -> None:
        """Avvia la connessione e il polling in background."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Ferma il polling e chiude la connessione."""
        ...

    @abstractmethod
    def get_status(self) -> PLCStatus:
        """Ritorna lo stato corrente del PLC (non bloccante)."""
        ...

    # -----------------------------------------------------------------------
    # Scrittura risultati sul PLC
    # -----------------------------------------------------------------------

    @abstractmethod
    def write_tracking_result(self, result: TrackingResult) -> None:
        ...

    @abstractmethod
    def write_orientation_result(self, result: OrientationResult) -> None:
        ...

    @abstractmethod
    def write_inspection_result(self, result: InspectionResult) -> None:
        ...

    # -----------------------------------------------------------------------
    # Helpers interni per firing delle callback
    # -----------------------------------------------------------------------

    def _fire_tracking(self) -> None:
        if self._cb_tracking:
            self._cb_tracking()

    def _fire_orientation(self) -> None:
        if self._cb_orientation:
            self._cb_orientation()

    def _fire_inspection(self) -> None:
        if self._cb_inspection:
            self._cb_inspection()

    def _fire_status(self, status: PLCStatus) -> None:
        if self._cb_status:
            self._cb_status(status)
