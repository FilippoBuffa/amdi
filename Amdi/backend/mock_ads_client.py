"""
Mock del client ADS per sviluppo e simulazione senza hardware PLC.

Funzionalità:
  - Trigger automatici a intervalli configurabili
  - Trigger manuali tramite metodi pubblici (chiamabili dall'API Flask)
  - Simulazione errori PLC
  - Stato macchina controllabile via codice
"""

from __future__ import annotations

import logging
import threading
import time
import random
from typing import Optional

from base_ads_client import (
    BaseADSClient,
    OrientationResult,
    PLCState,
    PLCStatus,
    TrackingResult,
    InspectionResult,
)

log = logging.getLogger(__name__)


class MockADSClient(BaseADSClient):
    """
    Client ADS simulato.

    Modalità auto: genera trigger a intervalli regolari imitando un PLC reale.
    Modalità manuale: i trigger vengono sparati solo su chiamata esplicita
                      (utile per testare l'HMI passo-passo).

    Esempio uso dall'API Flask:
        mock_client.trigger_tracking()        # simula trigger PLC cam1
        mock_client.set_machine_running(True)
        mock_client.simulate_error("test error")
    """

    def __init__(
        self,
        auto_trigger: bool = True,
        tracking_interval_s: float = 2.0,
        orientation_interval_s: float = 2.5,
        inspection_interval_s: float = 5.0,
    ) -> None:
        super().__init__()

        self._auto_trigger = auto_trigger
        self._intervals = {
            "tracking":    tracking_interval_s,
            "orientation": orientation_interval_s,
            "inspection":  inspection_interval_s,
        }

        self._status = PLCStatus(
            state=PLCState.DISCONNECTED,
            machine_running=False,
        )
        self._status_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

        # Registro dei risultati scritti (per ispezione/debug)
        self.written_tracking:    list[TrackingResult]    = []
        self.written_orientation: list[OrientationResult] = []
        self.written_inspection:  list[InspectionResult]  = []

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def start(self) -> None:
        log.info("MockADS: avvio (auto_trigger=%s)", self._auto_trigger)
        self._stop_event.clear()
        self._update_status(PLCState.CONNECTED, machine_running=True)

        if self._auto_trigger:
            for name, interval in self._intervals.items():
                t = threading.Thread(
                    target=self._auto_trigger_loop,
                    args=(name, interval),
                    name=f"mock-ads-{name}",
                    daemon=True,
                )
                self._threads.append(t)
                t.start()

        log.info("MockADS: avviato.")

    def stop(self) -> None:
        log.info("MockADS: stop.")
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self._threads.clear()
        self._update_status(PLCState.DISCONNECTED, machine_running=False)

    def get_status(self) -> PLCStatus:
        with self._status_lock:
            return self._status

    # -----------------------------------------------------------------------
    # Loop auto-trigger
    # -----------------------------------------------------------------------

    def _auto_trigger_loop(self, name: str, interval_s: float) -> None:
        """Thread dedicato per un singolo trigger automatico."""
        log.debug("MockADS: auto-trigger '%s' ogni %.1fs", name, interval_s)

        # Offset iniziale casuale per non far partire tutto insieme
        self._stop_event.wait(random.uniform(0.5, interval_s))

        while not self._stop_event.is_set():
            with self._status_lock:
                running = self._status.machine_running

            if running and self._auto_trigger:
                log.debug("MockADS: trigger automatico '%s'", name)
                self._fire(name)

            # Aggiungi piccolo jitter (±10%) per realismo
            jitter = interval_s * 0.1 * (random.random() * 2 - 1)
            self._stop_event.wait(interval_s + jitter)

    def _fire(self, name: str) -> None:
        if name == "tracking":
            self._fire_tracking()
        elif name == "orientation":
            self._fire_orientation()
        elif name == "inspection":
            self._fire_inspection()

    # -----------------------------------------------------------------------
    # Trigger manuali (chiamabili dall'API Flask / HMI)
    # -----------------------------------------------------------------------

    def trigger_tracking(self) -> None:
        """Simula un trigger manuale su CAM1."""
        log.info("MockADS: trigger manuale TRACKING")
        self._fire_tracking()

    def trigger_orientation(self) -> None:
        """Simula un trigger manuale su CAM2."""
        log.info("MockADS: trigger manuale ORIENTATION")
        self._fire_orientation()

    def trigger_inspection(self) -> None:
        """Simula un trigger manuale su CAM3."""
        log.info("MockADS: trigger manuale INSPECTION")
        self._fire_inspection()

    # -----------------------------------------------------------------------
    # Controllo stato macchina (callable dall'HMI)
    # -----------------------------------------------------------------------

    def set_machine_running(self, running: bool) -> None:
        """Avvia o ferma la macchina simulata."""
        log.info("MockADS: machine_running → %s", running)
        with self._status_lock:
            self._status = PLCStatus(
                state=self._status.state,
                machine_running=running,
                machine_error=self._status.machine_error,
            )
        self._fire_status(self._status)

    def simulate_error(self, message: str = "Simulated PLC error") -> None:
        """Simula un errore PLC."""
        log.warning("MockADS: errore simulato: %s", message)
        with self._status_lock:
            self._status = PLCStatus(
                state=PLCState.ERROR,
                machine_running=False,
                machine_error=True,
                error_message=message,
            )
        self._fire_status(self._status)

    def clear_error(self) -> None:
        """Resetta l'errore simulato."""
        log.info("MockADS: errore resettato.")
        self._update_status(PLCState.CONNECTED, machine_running=True)

    def set_auto_trigger(self, enabled: bool) -> None:
        """Abilita/disabilita i trigger automatici a runtime."""
        self._auto_trigger = enabled
        log.info("MockADS: auto_trigger → %s", enabled)

    # -----------------------------------------------------------------------
    # Scrittura risultati (registrati internamente per debug)
    # -----------------------------------------------------------------------

    def write_tracking_result(self, result: TrackingResult) -> None:
        self.written_tracking.append(result)
        log.debug(
            "MockADS: [WRITE] tracking (%.2f, %.2f) ok=%s",
            result.x, result.y, result.ok,
        )

    def write_orientation_result(self, result: OrientationResult) -> None:
        self.written_orientation.append(result)
        log.debug(
            "MockADS: [WRITE] orientation %.2f° ok=%s",
            result.angle, result.ok,
        )

    def write_inspection_result(self, result: InspectionResult) -> None:
        self.written_inspection.append(result)
        log.debug(
            "MockADS: [WRITE] inspection %s ok=%s",
            result.results, result.ok,
        )

    def get_written_results(self) -> dict:
        """Ritorna tutti i risultati scritti — utile per test e debug."""
        return {
            "tracking":    [{"x": r.x, "y": r.y, "ok": r.ok}     for r in self.written_tracking],
            "orientation": [{"angle": r.angle, "ok": r.ok}        for r in self.written_orientation],
            "inspection":  [{"results": r.results, "ok": r.ok}    for r in self.written_inspection],
        }

    # -----------------------------------------------------------------------
    # Helper privato
    # -----------------------------------------------------------------------

    def _update_status(
        self,
        state: PLCState,
        machine_running: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        with self._status_lock:
            self._status = PLCStatus(
                state=state,
                machine_running=machine_running,
                machine_error=(state == PLCState.ERROR),
                error_message=error_message,
            )
        self._fire_status(self._status)
