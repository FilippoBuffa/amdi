"""
Worker per la camera di ispezione.

Flusso:
  grab() bloccante → InspectionEngine (4 pezzi) → scrivi aResArray[1..4]
  → alza bResultsReady → attendi reset → loop
"""

from __future__ import annotations

import logging

from cameras.base_camera import CameraTimeoutError
from config import cam_cfg, vision_cfg
from inference.inspection_engine import InspectionEngine
from plc.variables import VARS
from workers.base_worker import BaseWorker

log = logging.getLogger(__name__)

# Mappa indice pezzo (1-based) → variabile PLC
_RES_VARS = {
    1: VARS.RES_ARRAY_1,
    2: VARS.RES_ARRAY_2,
    3: VARS.RES_ARRAY_3,
    4: VARS.RES_ARRAY_4,
}


class InspectionWorker(BaseWorker):

    def __init__(self, plc_client, camera=None) -> None:
        super().__init__(name="inspection", plc_client=plc_client)
        self._camera_override = camera
        self._camera = None
        self._engine: InspectionEngine | None = None

    # -----------------------------------------------------------------------
    # Implementazione BaseWorker
    # -----------------------------------------------------------------------

    def _init_camera(self) -> None:
        if self._camera_override:
            self._camera = self._camera_override
        else:
            self._camera = self._build_camera()

        self._camera.open()
        self._engine = InspectionEngine(
            model_path=vision_cfg.INSPECTION_MODEL_PATH,
        )
        log.info("[inspection] camera e InspectionEngine inizializzati.")

    def _ready_var(self) -> str:
        return VARS.INSPECTION_CAM_READY

    def _handshake_var(self) -> str:
        return VARS.RESULTS_READY

    def _grab_frame(self):
        try:
            return self._camera.grab(timeout_ms=60_000)
        except CameraTimeoutError:
            log.warning("[inspection] camera timeout — riprovo.")
            raise

    def _process_frame(self, frame) -> dict:
        result = self._engine.analyze(frame.image)

        # Scrivi i 4 risultati sul PLC (aResArray[1..4])
        for piece in result.pieces:
            var = _RES_VARS.get(piece.index)
            if var:
                self._plc.write(var, piece.ok, "BOOL")

        # Alza flag risultati pronti
        self._plc.write(VARS.RESULTS_READY, True, "BOOL")

        log.info(
            "[inspection] %d/4 OK | pezzi=%s | %.1fms",
            result.pass_count,
            [p.ok for p in result.pieces],
            result.inference_ms,
        )

        return {
            "pieces": [
                {
                    "index":       p.index,
                    "ok":          p.ok,
                    "confidence":  round(p.confidence, 3),
                    "defect_type": p.defect_type,
                }
                for p in result.pieces
            ],
            "all_ok":      result.ok,
            "pass_count":  result.pass_count,
            "fail_count":  result.fail_count,
            "inference_ms": round(result.inference_ms, 1),
            "frame_id":    frame.frame_id,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_camera(self):
        if cam_cfg.USE_REAL_CAMERAS:
            from cameras.basler_camera import BaslerCamera
            log.info("[inspection] connessione camera reale → %s", cam_cfg.IP_INSPECTION)
            return BaslerCamera(
                camera_id="inspection",
                ip=cam_cfg.IP_INSPECTION,
                exposure_us=cam_cfg.EXPOSURE_US,
                gain_db=cam_cfg.GAIN_DB,
            )
        else:
            from cameras.mock_camera import MockCamera
            return MockCamera(
                camera_id="inspection",
                trigger_interval_s=cam_cfg.MOCK_TRIGGER_INTERVAL_S,
            )

    def _on_stop_requested(self) -> None:
        if self._camera and hasattr(self._camera, "abort_grab"):
            self._camera.abort_grab()
        elif self._camera and hasattr(self._camera, "send_trigger"):
            self._camera.send_trigger()

    def _cleanup(self) -> None:
        if self._camera:
            try:
                self._camera.close()
            except Exception:
                pass
