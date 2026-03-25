"""
Implementazione reale del client ADS tramite PyADS.
Connessione a TwinCAT 3, lettura/scrittura variabili con tipi corretti.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import pyads

from .base_client import BasePLCClient, PLCState, PLCStatus

log = logging.getLogger(__name__)

# Mappa tipo stringa → costante pyads
_TYPE_MAP = {
    "BOOL": pyads.PLCTYPE_BOOL,
    "BYTE": pyads.PLCTYPE_USINT,    # BYTE TwinCAT = uint8
    "WORD": pyads.PLCTYPE_UINT,     # WORD TwinCAT = uint16
    "INT":  pyads.PLCTYPE_INT,
    "REAL": pyads.PLCTYPE_REAL,
    "LREAL": pyads.PLCTYPE_LREAL,
}


class ADSClient(BasePLCClient):
    """
    Client ADS reale per TwinCAT 3.

    Thread-safe: lock su ogni operazione read/write.
    Riconnessione automatica in caso di errore.
    """

    def __init__(self, ams_net_id: str, port: int = 851, ip_address: str = "", local_ams: str = "") -> None:
            self._ams_net_id  = ams_net_id
            self._port        = port
            self._ip_address  = ip_address
            self._local_ams   = local_ams
            self._plc: Optional[pyads.Connection] = None
            self._lock        = threading.Lock()
            self._status      = PLCStatus(state=PLCState.DISCONNECTED)
            self._status_lock = threading.Lock()
    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def start(self) -> None:
        log.info("ADS: connessione a %s:%d", self._ams_net_id, self._port)
        try:
            if self._local_ams:
                pyads.open_port()
                pyads.set_local_address(self._local_ams)
                pyads.close_port()
            self._plc = pyads.Connection(self._ams_net_id, self._port, self._ip_address or None)
            self._plc.open()
            self._set_status(PLCState.CONNECTED)
            log.info("ADS: connesso.")
        except Exception as exc:
            log.error("ADS: errore connessione: %s", exc)
            self._set_status(PLCState.ERROR, str(exc))
            raise

    def stop(self) -> None:
        log.info("ADS: disconnessione.")
        if self._plc:
            try:
                self._plc.close()
            except Exception:
                pass
        self._set_status(PLCState.DISCONNECTED)

    def get_status(self) -> PLCStatus:
        with self._status_lock:
            return self._status

    # -----------------------------------------------------------------------
    # Read / Write
    # -----------------------------------------------------------------------

    def reconnect(self) -> None:
        """Tenta di riconnettersi (usato dal monitor se la connessione cade)."""
        log.info("ADS: tentativo riconnessione...")
        if self._plc:
            try:
                self._plc.close()
            except Exception:
                pass
        self._plc = None
        self.start()

    def read(self, var_name: str, plc_type: str) -> Any:
        if self._plc is None:
            raise ConnectionError("ADS non connesso")
        ads_type = self._resolve_type(plc_type)
        with self._lock:
            try:
                return self._plc.read_by_name(var_name, ads_type)
            except Exception as exc:
                log.error("ADS read [%s] failed: %s", var_name, exc)
                self._set_status(PLCState.ERROR, str(exc))
                raise

    def write(self, var_name: str, value: Any, plc_type: str) -> None:
        if self._plc is None:
            raise ConnectionError("ADS non connesso")
        ads_type = self._resolve_type(plc_type)
        with self._lock:
            try:
                self._plc.write_by_name(var_name, value, ads_type)
                log.debug("ADS write [%s] = %s", var_name, value)
            except Exception as exc:
                log.error("ADS write [%s] failed: %s", var_name, exc)
                self._set_status(PLCState.ERROR, str(exc))
                raise

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _resolve_type(self, plc_type: str):
        t = _TYPE_MAP.get(plc_type.upper())
        if t is None:
            raise ValueError(f"Tipo ADS sconosciuto: {plc_type}")
        return t

    def _set_status(self, state: PLCState, msg: Optional[str] = None) -> None:
        with self._status_lock:
            self._status = PLCStatus(state=state, error_message=msg)
