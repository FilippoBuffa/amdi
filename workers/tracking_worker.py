"""
Worker per la camera di tracking.

Flusso:
  grab() bloccante → YOLO → miglior pezzo → scrivi X/Y → alza bCoordinateReady
  → attendi reset → loop
"""

from __future__ import annotations

import logging

from cameras.base_camera import CameraTimeoutError
from config import cam_cfg, vision_cfg
from inference.yolo_engine import YoloEngine
from plc.variables import VARS
from workers.base_worker import BaseWorker

log = logging.getLogger(__name__)


class TrackingWorker(BaseWorker):

    def __init__(self, plc_client, camera=None) -> None:
        super().__init__(name="tracking", plc_client=plc_client)
        self._camera_override = camera   # iniettato dall'orchestratore (o mock)
        self._camera = None
        self._engine: YoloEngine | None = None

    # -----------------------------------------------------------------------
    # Implementazione BaseWorker
    # -----------------------------------------------------------------------

    def _init_camera(self) -> None:
        if self._camera_override:
            self._camera = self._camera_override
        else:
            self._camera = self._build_camera()

        self._camera.open()

        self._engine = YoloEngine(
            model_path=vision_cfg.YOLO_MODEL_PATH,
            conf_min=vision_cfg.YOLO_CONF_MIN,
            px_to_centimm=vision_cfg.PX_TO_CENTIMM_SCALE,
            image_center_x=vision_cfg.IMAGE_CENTER_X_PX,
            image_center_y=vision_cfg.IMAGE_CENTER_Y_PX,
        )
        log.info("[tracking] camera e YOLO engine inizializzati.")

    def _ready_var(self) -> str:
        return VARS.TRACKING_CAM_READY

    def _handshake_var(self) -> str:
        return VARS.COORDINATE_READY

    def _grab_frame(self):
        try:
            return self._camera.grab(timeout_ms=60_000)
        except CameraTimeoutError:
            log.warning("[tracking] camera timeout — riprovo.")
            raise

    def _process_frame(self, frame) -> dict:
        result = self._engine.analyze(frame.image)

        if result.ok:
            # TODO: rimuovere coordinate fisse quando il robot è calibrato
            safe_x = 1700
            safe_y = 28000
            self._plc.write(VARS.COORDINATE_X, safe_x, "WORD")
            self._plc.write(VARS.COORDINATE_Y, safe_y, "WORD")
            self._plc.write(VARS.COORDINATE_READY, True, "BOOL")
            log.info(
                "[tracking] pezzo: X=%d Y=%d centimm (fixed safe pos) | conf=%.2f | %.1fms",
                safe_x, safe_y,
                result.confidence, result.inference_ms,
            )
        else:
            log.warning("[tracking] nessun pezzo trovato — frame ignorato.")

        return {
            "x_centimm":   result.x_centimm,
            "y_centimm":   result.y_centimm,
            "confidence":  round(result.confidence, 3),
            "ok":          result.ok,
            "detections":  len(result.detections),
            "inference_ms": round(result.inference_ms, 1),
            "frame_id":    frame.frame_id,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_camera(self):
        if cam_cfg.USE_REAL_CAMERAS:
            from cameras.basler_camera import BaslerCamera
            log.info("[tracking] connessione camera reale → %s", cam_cfg.IP_TRACKING)
            return BaslerCamera(
                camera_id="tracking",
                ip=cam_cfg.IP_TRACKING,
                exposure_us=cam_cfg.EXPOSURE_US,
                gain_db=cam_cfg.GAIN_DB,
            )
        else:
            from cameras.mock_camera import MockCamera
            return MockCamera(
                camera_id="tracking",
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
