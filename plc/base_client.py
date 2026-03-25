"""
Interfaccia astratta per la comunicazione con il PLC.
Il client reale (PyADS) e il mock implementano questa classe.
Il resto del codice dipende SOLO da questa interfaccia.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class PLCState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED    = "connected"
    ERROR        = "error"


@dataclass
class PLCStatus:
    state:         PLCState        = PLCState.DISCONNECTED
    error_message: Optional[str]   = None

    @property
    def is_ok(self) -> bool:
        return self.state == PLCState.CONNECTED


class BasePLCClient(ABC):
    """
    Interfaccia minimale per lettura/scrittura variabili ADS.

    Pattern:
        client.start()
        client.write(VARS.COORDINATE_X, 1250, "WORD")
        val = client.read(VARS.COORDINATE_READY, "BOOL")
        client.stop()
    """

    @abstractmethod
    def start(self) -> None:
        """Apre la connessione."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Chiude la connessione."""
        ...

    @abstractmethod
    def get_status(self) -> PLCStatus:
        """Stato corrente della connessione."""
        ...

    @abstractmethod
    def read(self, var_name: str, plc_type: str) -> Any:
        """
        Legge una variabile dal PLC.

        plc_type: "BOOL" | "WORD" | "BYTE" | "INT" | "REAL"
        Restituisce il valore Python corrispondente.
        """
        ...

    @abstractmethod
    def write(self, var_name: str, value: Any, plc_type: str) -> None:
        """
        Scrive una variabile sul PLC.

        plc_type: "BOOL" | "WORD" | "BYTE" | "INT" | "REAL"
        """
        ...
