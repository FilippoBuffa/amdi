"""
Implementazione reale del client ADS tramite PyADS.
Connessione a TwinCAT 3, polling variabili trigger in un thread dedicato.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import pyads

from .base_ads_client import (
    BaseADSClient,
    OrientationResult,
    PLCState,
    PLCStatus,
    TrackingResult,
    InspectionResult,
)
from .ads_variables import VARS, ADS_TYPE_MAP

log = logging.getLogger(__name__)


class ADSClient(BaseADSClient):
    """
    Client ADS reale.

    - Si connette al PLC TwinCAT 3 tramite AMS Net ID + porta.
    - Fa polling delle variabili trigger in un thread separato.
    - Quando rileva un fronte di salita (False→True) su un trigger,
      chiama la callback registrata e resetta la variabile a False.
    - Scrive i risultati vision direttamente sulle variabili ADS.
    """

    def __init__(
        self,
        ams_net_id: str,
        port: int = 851,
        poll_interval_ms: int = 10,
    ) -> None:
        super().__init__()
        self._ams_net_id = ams_net_id
        self._port = port
        self._poll_interval_s = poll_interval_ms / 1000.0

        self._plc: Optional[pyads.Connection] = None
        self._status = PLCStatus(state=PLCState.DISCONNECTED)
        self._status_lock = threading.Lock()

        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Stato precedente dei trigger per rilevare fronti di salita
        self._prev_trigger = {
            VARS.TRIGGER_TRACKING:    False,
            VARS.TRIGGER_ORIENTATION: False,
            VARS.TRIGGER_INSPECTION:  False,
        }

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Apre la connessione ADS e avvia il thread di polling."""
        log.info("ADS: connessione a %s:%d", self._ams_net_id, self._port)
        try:
            self._plc = pyads.Connection(self._ams_net_id, self._port)
            self._plc.open()
            self._update_status(PLCState.CONNECTED)
            log.info("ADS: connesso.")
        except Exception as exc:
            log.error("ADS: errore connessione: %s", exc)
            self._update_status(PLCState.ERROR, str(exc))
            return

        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="ads-poll",
            daemon=True,
        )
        self._poll_thread.start()

    def stop(self) -> None:
        """Ferma il polling e chiude la connessione."""
        log.info("ADS: stop richiesto.")
        self._stop_event.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=3.0)
        if self._plc:
            try:
                self._plc.close()
            except Exception:
                pass
        self._update_status(PLCState.DISCONNECTED)
        log.info("ADS: disconnesso.")

    def get_status(self) -> PLCStatus:
        with self._status_lock:
            return self._status

    # -----------------------------------------------------------------------
    # Thread di polling
    # -----------------------------------------------------------------------

    def _poll_loop(self) -> None:
        log.debug("ADS poll loop avviato.")
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:
                log.error("ADS: errore polling: %s", exc)
                self._update_status(PLCState.ERROR, str(exc))
                # Attendi un secondo prima di riprovare
                self._stop_event.wait(1.0)
                self._try_reconnect()
            else:
                self._stop_event.wait(self._poll_interval_s)

    def _poll_once(self) -> None:
        """Legge trigger e stato macchina in un singolo ciclo."""
        # --- Stato macchina ---
        running = self._plc.read_by_name(VARS.MACHINE_RUNNING, pyads.PLCTYPE_BOOL)
        error   = self._plc.read_by_name(VARS.MACHINE_ERROR,   pyads.PLCTYPE_BOOL)

        new_state = PLCState.ERROR if error else PLCState.CONNECTED
        with self._status_lock:
            changed = (
                self._status.state != new_state
                or self._status.machine_running != running
                or self._status.machine_error != error
            )
            self._status = PLCStatus(
                state=new_state,
                machine_running=running,
                machine_error=error,
            )

        if changed:
            self._fire_status(self._status)

        # --- Trigger con rilevamento fronte ---
        triggers = {
            VARS.TRIGGER_TRACKING:    self._fire_tracking,
            VARS.TRIGGER_ORIENTATION: self._fire_orientation,
            VARS.TRIGGER_INSPECTION:  self._fire_inspection,
        }
        for var, fire_fn in triggers.items():
            current = self._plc.read_by_name(var, pyads.PLCTYPE_BOOL)
            if current and not self._prev_trigger[var]:
                log.debug("ADS: trigger rilevato su %s", var)
                fire_fn()
                # Reset handshake: scrivi False per confermare ricezione
                self._plc.write_by_name(var, False, pyads.PLCTYPE_BOOL)
            self._prev_trigger[var] = current

    def _try_reconnect(self) -> None:
        """Tenta riconnessione dopo errore."""
        log.info("ADS: tentativo riconnessione...")
        try:
            if self._plc:
                self._plc.close()
            self._plc = pyads.Connection(self._ams_net_id, self._port)
            self._plc.open()
            self._update_status(PLCState.CONNECTED)
            log.info("ADS: riconnesso.")
        except Exception as exc:
            log.error("ADS: riconnessione fallita: %s", exc)
            self._update_status(PLCState.ERROR, str(exc))

    # -----------------------------------------------------------------------
    # Scrittura risultati
    # -----------------------------------------------------------------------

    def write_tracking_result(self, result: TrackingResult) -> None:
        if not self._plc:
            return
        try:
            self._plc.write_by_name(VARS.RESULT_TRACKING_X,  result.x,  pyads.PLCTYPE_LREAL)
            self._plc.write_by_name(VARS.RESULT_TRACKING_Y,  result.y,  pyads.PLCTYPE_LREAL)
            self._plc.write_by_name(VARS.RESULT_TRACKING_OK, result.ok, pyads.PLCTYPE_BOOL)
            log.debug("ADS: tracking scritto (%.2f, %.2f) ok=%s", result.x, result.y, result.ok)
        except Exception as exc:
            log.error("ADS: errore scrittura tracking: %s", exc)

    def write_orientation_result(self, result: OrientationResult) -> None:
        if not self._plc:
            return
        try:
            self._plc.write_by_name(VARS.RESULT_ANGLE,          result.angle, pyads.PLCTYPE_LREAL)
            self._plc.write_by_name(VARS.RESULT_ORIENTATION_OK, result.ok,    pyads.PLCTYPE_BOOL)
            log.debug("ADS: orientamento scritto %.2f° ok=%s", result.angle, result.ok)
        except Exception as exc:
            log.error("ADS: errore scrittura orientamento: %s", exc)

    def write_inspection_result(self, result: InspectionResult) -> None:
        if not self._plc:
            return
        try:
            inspection_vars = [
                VARS.RESULT_INSPECTION_0,
                VARS.RESULT_INSPECTION_1,
                VARS.RESULT_INSPECTION_2,
                VARS.RESULT_INSPECTION_3,
            ]
            for i, var in enumerate(inspection_vars):
                value = result.results[i] if i < len(result.results) else False
                self._plc.write_by_name(var, value, pyads.PLCTYPE_BOOL)
            # Handshake: segnala al PLC che i dati sono pronti
            self._plc.write_by_name(VARS.RESULT_INSPECTION_OK, True, pyads.PLCTYPE_BOOL)
            log.debug("ADS: ispezione scritta %s", result.results)
        except Exception as exc:
            log.error("ADS: errore scrittura ispezione: %s", exc)

    # -----------------------------------------------------------------------
    # Helpers privati
    # -----------------------------------------------------------------------

    def _update_status(
        self,
        state: PLCState,
        error_message: Optional[str] = None,
    ) -> None:
        with self._status_lock:
            self._status = PLCStatus(
                state=state,
                machine_running=self._status.machine_running,
                machine_error=(state == PLCState.ERROR),
                error_message=error_message,
            )
        self._fire_status(self._status)
