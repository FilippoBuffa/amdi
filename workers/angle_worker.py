"""
Worker per la camera angolo.

Flusso:
  grab() bloccante → AngleEngine → angolo int → scrivi iCoordinateA
  → alza bAngleReady → attendi reset → loop
"""

from __future__ import annotations

import logging

from cameras.base_camera import CameraTimeoutError
from config import cam_cfg, vision_cfg
from inference.angle_engine import AngleEngine
from plc.variables import VARS
from workers.base_worker import BaseWorker

log = logging.getLogger(__name__)


class AngleWorker(BaseWorker):

    def __init__(self, plc_client, camera=None) -> None:
        super().__init__(name="angle", plc_client=plc_client)
        self._camera_override = camera
        self._camera = None
        self._engine: AngleEngine | None = None

    # -----------------------------------------------------------------------
    # Implementazione BaseWorker
    # -----------------------------------------------------------------------

    def _init_camera(self) -> None:
        if self._camera_override:
            self._camera = self._camera_override
        else:
            self._camera = self._build_camera()

        self._camera.open()
        self._engine = AngleEngine(model_path=vision_cfg.ANGLE_MODEL_PATH)
        log.info("[angle] camera e AngleEngine inizializzati.")

    def _ready_var(self) -> str:
        return VARS.ANGLE_CAM_READY

    def _handshake_var(self) -> str:
        return VARS.ANGLE_READY

    def _grab_frame(self):
        try:
            return self._camera.grab(timeout_ms=60_000)
        except CameraTimeoutError:
            log.warning("[angle] camera timeout — riprovo.")
            raise

    def _process_frame(self, frame) -> dict:
        result = self._engine.analyze(frame.image)

        if result.ok:
            # BYTE PLC: clamp 0-255 (angolo in gradi, normalmente 0-359 ma BYTE è 0-255)
            # Converti angolo > 255 se necessario (es. modulo 256 o scaling)
            angle_byte = result.angle_deg % 256
            self._plc.write(VARS.COORDINATE_A, angle_byte, "BYTE")
            self._plc.write(VARS.ANGLE_READY, True, "BOOL")
            log.info(
                "[angle] angolo=%d° (byte=%d) conf=%.2f | %.1fms",
                result.angle_deg, angle_byte, result.confidence, result.inference_ms,
            )
        else:
            log.warning("[angle] stima angolo fallita — frame ignorato.")

        return {
            "angle_deg":   result.angle_deg,
            "confidence":  round(result.confidence, 3),
            "ok":          result.ok,
            "inference_ms": round(result.inference_ms, 1),
            "frame_id":    frame.frame_id,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_camera(self):
        if cam_cfg.USE_REAL_CAMERAS:
            from cameras.basler_camera import BaslerCamera
            log.info("[angle] connessione camera reale → %s", cam_cfg.IP_ANGLE)
            return BaslerCamera(
                camera_id="angle",
                ip=cam_cfg.IP_ANGLE,
                exposure_us=cam_cfg.EXPOSURE_US,
                gain_db=cam_cfg.GAIN_DB,
            )
        else:
            from cameras.mock_camera import MockCamera
            return MockCamera(
                camera_id="angle",
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
