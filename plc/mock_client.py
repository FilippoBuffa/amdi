"""
Mock del client PLC per sviluppo senza hardware TwinCAT.

Comportamento simulato:
  - Mantiene un dizionario in-memory delle variabili
  - Quando il backend scrive TRUE su un flag "ready" (es. bCoordinateReady),
    il mock simula il PLC che legge e resetta il flag a FALSE dopo N secondi
  - Espone trigger_manual() per far scattare eventi dal Flask API
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from .base_client import BasePLCClient, PLCState, PLCStatus
from .variables import VARS

log = logging.getLogger(__name__)

# Flag "ready" che il PLC deve resettare dopo aver letto
_HANDSHAKE_FLAGS = {
    VARS.COORDINATE_READY,
    VARS.ANGLE_READY,
    VARS.RESULTS_READY,
}


class MockPLCClient(BasePLCClient):
    """
    Client PLC simulato.

    Thread-safe. Simula il reset dei flag handshake come farebbe il PLC reale.
    """

    def __init__(self, plc_read_delay_s: float = 1.5) -> None:
        self._plc_read_delay = plc_read_delay_s
        self._lock    = threading.Lock()
        self._running = False

        # Stato iniziale di tutte le variabili
        self._store: Dict[str, Any] = {
            # --- Cam ready (Python → PLC) ---
            VARS.TRACKING_CAM_READY:   False,
            VARS.ANGLE_CAM_READY:      False,
            VARS.INSPECTION_CAM_READY: False,
            VARS.CALIBRATION_READY:    False,

            # --- Risultati ---
            VARS.COORDINATE_X: 0,
            VARS.COORDINATE_Y: 0,
            VARS.COORDINATE_A: 0,
            VARS.RES_ARRAY_1:  False,
            VARS.RES_ARRAY_2:  False,
            VARS.RES_ARRAY_3:  False,
            VARS.RES_ARRAY_4:  False,

            # --- Handshake ---
            VARS.COORDINATE_READY: False,
            VARS.ANGLE_READY:      False,
            VARS.RESULTS_READY:    False,

            # --- PLC → Python ---
            VARS.WATCHDOG:            False,
            VARS.QR_CODE_SCANNED:     False,
            VARS.CALIBRATION_REQUEST: False,

            # --- Stato macchina ---
            VARS.MACHINE_STATE:       0,     # IDLE
            VARS.BTN_RESET_INHIBITED: False,
            VARS.STATUS_REQUEST:      0,

            # --- Bottoni virtuali ---
            VARS.BTN_START:           False,
            VARS.BTN_STOP:            False,
            VARS.BTN_RESET:           False,

            # --- Statistiche ciclo (PLC → Python) ---
            VARS.LEAK_TEST_1:   False,
            VARS.LEAK_TEST_2:   False,
            VARS.LEAK_TEST_3:   False,
            VARS.LEAK_TEST_4:   False,

            VARS.FLOW_TEST_1:   False,
            VARS.FLOW_TEST_2:   False,
            VARS.FLOW_TEST_3:   False,
            VARS.FLOW_TEST_4:   False,

            VARS.INSPECT_CAM_1: False,
            VARS.INSPECT_CAM_2: False,
            VARS.INSPECT_CAM_3: False,
            VARS.INSPECT_CAM_4: False,

            VARS.ALL_CLUSTER_1: False,
            VARS.ALL_CLUSTER_2: False,
            VARS.ALL_CLUSTER_3: False,
            VARS.ALL_CLUSTER_4: False,
        }

        self._status = PLCStatus(state=PLCState.DISCONNECTED)

        # Callback opzionale per notificare scritture (usata dai test / HMI)
        self._write_callbacks: dict = {}

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._status  = PLCStatus(state=PLCState.CONNECTED)
        log.info("MockPLC: avviato (plc_read_delay=%.1fs)", self._plc_read_delay)

    def stop(self) -> None:
        self._running = False
        self._status  = PLCStatus(state=PLCState.DISCONNECTED)
        log.info("MockPLC: fermato.")

    def get_status(self) -> PLCStatus:
        return self._status

    # -----------------------------------------------------------------------
    # Read / Write
    # -----------------------------------------------------------------------

    def read(self, var_name: str, plc_type: str) -> Any:
        with self._lock:
            val = self._store.get(var_name)
        log.debug("MockPLC read  [%s] = %s", var_name, val)
        return val

    def write(self, var_name: str, value: Any, plc_type: str) -> None:
        with self._lock:
            self._store[var_name] = value
        log.debug("MockPLC write [%s] = %s", var_name, value)

        # Se il backend alza un flag handshake, simula il PLC che lo resetta
        if var_name in _HANDSHAKE_FLAGS and value is True:
            self._schedule_reset(var_name)

        # Callback opzionale
        cb = self._write_callbacks.get(var_name)
        if cb:
            cb(value)

    # -----------------------------------------------------------------------
    # API per Flask / test: forza lettura / scrittura lato "PLC"
    # -----------------------------------------------------------------------

    def plc_set(self, var_name: str, value: Any) -> None:
        """Simula il PLC che scrive una variabile (es. bCalibrationRequest)."""
        with self._lock:
            self._store[var_name] = value
        log.info("MockPLC [PLC-side] set [%s] = %s", var_name, value)

    def get_all(self) -> dict:
        """Snapshot di tutto lo store (per debug/HMI)."""
        with self._lock:
            return dict(self._store)

    def on_write(self, var_name: str, callback) -> None:
        """Registra una callback chiamata quando var_name viene scritta dal backend."""
        self._write_callbacks[var_name] = callback

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _schedule_reset(self, var_name: str) -> None:
        """Lancia un thread che dopo N secondi resetta il flag a FALSE."""
        def _reset():
            time.sleep(self._plc_read_delay)
            with self._lock:
                self._store[var_name] = False
            log.debug("MockPLC: auto-reset [%s] → False", var_name)

        t = threading.Thread(target=_reset, daemon=True, name=f"mock-reset-{var_name}")
        t.start()
