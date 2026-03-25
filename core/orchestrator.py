"""
Orchestratore: avvia e supervisiona tutti i componenti del sistema.

Responsabilità:
  - Crea il client PLC (reale o mock in base alla config)
  - Monitora iMachineState: avvia i worker SOLO quando la macchina è in AUTOMATIC (10)
  - Ferma i worker se la macchina esce da AUTOMATIC
  - Espone metodi di controllo per il Flask API
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from config import ads_cfg, cam_cfg
from core.event_log import event_log
from plc.variables import VARS
from workers.tracking_worker import TrackingWorker
from workers.angle_worker import AngleWorker
from workers.inspection_worker import InspectionWorker

log = logging.getLogger(__name__)

MACHINE_AUTOMATIC = 10   # iMachineState: produzione in corso

# Mappa gruppi statistiche → variabili PLC
_STATS_GROUPS = {
    "leak":    [VARS.LEAK_TEST_1,   VARS.LEAK_TEST_2,   VARS.LEAK_TEST_3,   VARS.LEAK_TEST_4],
    "flow":    [VARS.FLOW_TEST_1,   VARS.FLOW_TEST_2,   VARS.FLOW_TEST_3,   VARS.FLOW_TEST_4],
    "inspect": [VARS.INSPECT_CAM_1, VARS.INSPECT_CAM_2, VARS.INSPECT_CAM_3, VARS.INSPECT_CAM_4],
    "cluster": [VARS.ALL_CLUSTER_1, VARS.ALL_CLUSTER_2, VARS.ALL_CLUSTER_3, VARS.ALL_CLUSTER_4],
}


class Orchestrator:
    """
    Punto di ingresso dell'intero sistema.

    Uso:
        orch = Orchestrator()
        orch.start()
        ...
        orch.stop()
    """

    def __init__(self) -> None:
        self._plc             = self._build_plc_client()
        self._tracking:    Optional[TrackingWorker]   = None
        self._angle:       Optional[AngleWorker]      = None
        self._inspection:  Optional[InspectionWorker] = None
        self._running         = False
        self._workers_started = False
        self._lock            = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        log.info("Orchestrator: avvio sistema...")
        event_log.info("system", "Avvio sistema AmdiApp")

        # Connetti PLC
        try:
            self._plc.start()
            event_log.info("system", "PLC connesso", {"status": str(self._plc.get_status())})
        except Exception as exc:
            log.error("Orchestrator: connessione PLC fallita: %s", exc)
            event_log.error("system", f"Connessione PLC fallita: {exc}")

        # Avvia monitor: i worker partono SOLO quando la macchina entra in AUTOMATIC
        self._monitor_thread = threading.Thread(
            target=self._state_monitor,
            name="state-monitor",
            daemon=True,
        )
        self._monitor_thread.start()
        log.info("Orchestrator: in attesa di iMachineState == %d (AUTOMATIC)...", MACHINE_AUTOMATIC)
        event_log.info("system", f"In attesa dello stato AUTOMATIC ({MACHINE_AUTOMATIC}) per aprire le telecamere")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False

        log.info("Orchestrator: stop sistema...")
        event_log.info("system", "Stop sistema AmdiApp")

        self._stop_workers()

        try:
            self._plc.stop()
        except Exception:
            pass

        log.info("Orchestrator: sistema fermato.")

    # -----------------------------------------------------------------------
    # Monitor stato macchina
    # -----------------------------------------------------------------------

    def _state_monitor(self) -> None:
        """
        Polling di iMachineState.
        - Quando entra in AUTOMATIC (10) → avvia i worker (apre le telecamere)
        - Quando esce da AUTOMATIC       → ferma i worker (chiude le telecamere)
        """
        while self._running:
            try:
                state = self._plc.read(VARS.MACHINE_STATE, "INT") or 0

                if state == MACHINE_AUTOMATIC and not self._workers_started:
                    log.info("Orchestrator: AUTOMATIC rilevato → avvio worker + telecamere")
                    event_log.info("system", "Macchina in AUTOMATIC — connessione telecamere")
                    self._start_workers()

                elif state != MACHINE_AUTOMATIC and self._workers_started:
                    log.info("Orchestrator: uscita da AUTOMATIC (stato=%d) → stop worker", state)
                    event_log.info("system", f"Macchina uscita da AUTOMATIC (stato {state}) — disconnessione telecamere")
                    self._stop_workers()

            except Exception as exc:
                log.warning("Orchestrator: errore lettura iMachineState: %s", exc)

            time.sleep(0.5)

    def _start_workers(self) -> None:
        with self._lock:
            if self._workers_started:
                return
            self._workers_started = True

        self._tracking   = TrackingWorker(plc_client=self._plc)
        self._angle      = AngleWorker(plc_client=self._plc)
        self._inspection = InspectionWorker(plc_client=self._plc)

        for worker in [self._tracking, self._angle, self._inspection]:
            try:
                worker.start()
                event_log.info("system", f"Worker [{worker.name}] avviato")
            except Exception as exc:
                log.error("Orchestrator: errore avvio worker %s: %s", worker.name, exc)
                event_log.error("system", f"Errore avvio worker [{worker.name}]: {exc}")

    def _stop_workers(self) -> None:
        with self._lock:
            if not self._workers_started:
                return
            self._workers_started = False

        for worker in [self._tracking, self._angle, self._inspection]:
            if worker:
                try:
                    worker.stop()
                    event_log.info("system", f"Worker [{worker.name}] fermato")
                except Exception as exc:
                    log.error("Errore stop worker: %s", exc)

        self._tracking   = None
        self._angle      = None
        self._inspection = None

    # -----------------------------------------------------------------------
    # Stato (per Flask API)
    # -----------------------------------------------------------------------

    def get_system_status(self) -> dict:
        """Snapshot completo dello stato per l'HMI."""
        plc_status = self._plc.get_status()

        workers = {}
        for name, worker in [
            ("tracking",   self._tracking),
            ("angle",      self._angle),
            ("inspection", self._inspection),
        ]:
            if worker:
                s = worker.get_status()
                workers[name] = {
                    "state":         s.state.value,
                    "frame_count":   s.frame_count,
                    "error_count":   s.error_count,
                    "last_error":    s.last_error,
                    "last_result":   s.last_result,
                    "last_frame_ts": s.last_frame_ts,
                    "inference_ms":  s.inference_ms,
                }
            else:
                workers[name] = {"state": "waiting_start"}

        plc_vars = {}
        if hasattr(self._plc, "get_all"):
            plc_vars = self._plc.get_all()

        machine_state   = 0
        reset_inhibited = False
        statistics      = {}

        if plc_status.is_ok:
            try:
                machine_state   = self._plc.read(VARS.MACHINE_STATE,       "INT")  or 0
                reset_inhibited = self._plc.read(VARS.BTN_RESET_INHIBITED, "BOOL") or False
            except Exception:
                pass

            # Leggi statistiche ciclo
            for group, vars_list in _STATS_GROUPS.items():
                values = []
                for var in vars_list:
                    try:
                        values.append(bool(self._plc.read(var, "BOOL")))
                    except Exception:
                        values.append(None)
                statistics[group] = values

        return {
            "running":          self._running,
            "workers_started":  self._workers_started,
            "machine_state":    machine_state,
            "reset_inhibited":  reset_inhibited,
            "plc": {
                "state":   plc_status.state.value,
                "ok":      plc_status.is_ok,
                "error":   plc_status.error_message,
            },
            "workers":     workers,
            "statistics":  statistics,
            "plc_vars":    plc_vars,
        }

    # -----------------------------------------------------------------------
    # Controllo manuale (Flask API → test senza PLC fisico)
    # -----------------------------------------------------------------------

    def manual_trigger(self, camera: str) -> dict:
        """Invia un trigger manuale a una camera specifica (solo MockCamera)."""
        worker_map = {
            "tracking":   self._tracking,
            "angle":      self._angle,
            "inspection": self._inspection,
        }
        worker = worker_map.get(camera)
        if not worker:
            return {"ok": False, "error": f"Camera '{camera}' non trovata o worker non avviato."}

        cam = getattr(worker, "_camera", None)
        if cam and hasattr(cam, "send_trigger"):
            cam.send_trigger()
            event_log.info("system", f"Trigger manuale → [{camera}]")
            return {"ok": True, "camera": camera}
        else:
            return {"ok": False, "error": "Camera non supporta trigger manuale."}

    def plc_set(self, var_name: str, value) -> dict:
        """Scrive una variabile sul PLC (mock o reale)."""
        try:
            if isinstance(value, bool):
                plc_type = "BOOL"
            else:
                plc_type = "INT"
                value = int(value)
            self._plc.write(var_name, value, plc_type)
            event_log.info("system", f"PLC write: {var_name} = {value}")
            return {"ok": True, "var": var_name, "value": value}
        except Exception as exc:
            log.error("plc_set error: %s", exc)
            return {"ok": False, "error": str(exc)}

    # -----------------------------------------------------------------------
    # Factory PLC
    # -----------------------------------------------------------------------

    def _build_plc_client(self):
        if ads_cfg.USE_MOCK:
            from plc.mock_client import MockPLCClient
            log.info("Orchestrator: uso MockPLCClient (ADS_USE_MOCK=true)")
            return MockPLCClient(plc_read_delay_s=ads_cfg.MOCK_PLC_READ_DELAY_S)
        else:
            from plc.ads_client import ADSClient
            log.info("Orchestrator: uso ADSClient → %s:%d", ads_cfg.AMS_NET_ID, ads_cfg.PORT)
            return ADSClient(ads_cfg.AMS_NET_ID, ads_cfg.PORT,
                             ip_address=ads_cfg.PLC_IP,
                             local_ams=ads_cfg.PLC_LOCAL_AMS)

    @property
    def plc(self):
        return self._plc
