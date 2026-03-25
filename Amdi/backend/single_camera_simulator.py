"""
single_camera_simulator.py
==========================
Usa una singola telecamera Basler fisica per simulare tutti e 3 gli stage.

Ogni stage fa un grab reale dalla camera — utile per sviluppare e testare
gli algoritmi vision con immagini vere prima di avere i 3 Basler definitivi.

Uso:
    from single_camera_simulator import SingleCameraSimulator

    sim = SingleCameraSimulator(ip="192.168.1.2")
    sim.open()

    frame = sim.grab_tracking()     # grab per stage 1
    frame = sim.grab_orientation()  # grab per stage 2
    frame = sim.grab_inspection()   # grab per stage 3

    sim.close()

Implementa anche BaseCamera per essere usato direttamente
al posto di MockCamera negli script di test:

    sim_as_cam = sim.as_camera("tracking")
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from base_camera import BaseCamera, CameraInfo, CameraState, Frame, CameraError
from basler_camera import BaslerCamera

log = logging.getLogger(__name__)


class SingleCameraSimulator:
    """
    Wrappa una singola BaslerCamera e la espone come 3 camere logiche.
    Un lock garantisce che i grab non si sovrappongano.
    """

    def __init__(
        self,
        ip: Optional[str] = None,
        serial: Optional[str] = None,
        exposure_us: float = 10000.0,
        gain_db: float = 0.0,
    ) -> None:
        self._camera = BaslerCamera(
            camera_id="simulator",
            ip=ip,
            serial=serial,
            exposure_us=exposure_us,
            gain_db=gain_db,
        )
        self._lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def open(self) -> None:
        self._camera.open()
        log.info("SingleCameraSimulator: pronto.")

    def close(self) -> None:
        self._camera.close()
        log.info("SingleCameraSimulator: chiuso.")

    def __enter__(self) -> "SingleCameraSimulator":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # -----------------------------------------------------------------------
    # Grab per stage — tutti usano la stessa camera fisica
    # -----------------------------------------------------------------------

    def grab_tracking(self, timeout_ms: int = 5000) -> Frame:
        """Grab per stage 1 - Tracking."""
        return self._grab("tracking", timeout_ms)

    def grab_orientation(self, timeout_ms: int = 5000) -> Frame:
        """Grab per stage 2 - Orientation."""
        return self._grab("orientation", timeout_ms)

    def grab_inspection(self, timeout_ms: int = 5000) -> Frame:
        """Grab per stage 3 - Inspection."""
        return self._grab("inspection", timeout_ms)

    def _grab(self, stage: str, timeout_ms: int) -> Frame:
        with self._lock:
            frame = self._camera.grab(timeout_ms)
            # Riassegna il camera_id con lo stage logico
            # così il resto del codice sa da quale stage arriva il frame
            frame.camera_id = stage
            return frame

    # -----------------------------------------------------------------------
    # Parametri (applicati alla camera fisica)
    # -----------------------------------------------------------------------

    def set_exposure(self, exposure_us: float) -> None:
        self._camera.set_exposure(exposure_us)

    def set_gain(self, gain_db: float) -> None:
        self._camera.set_gain(gain_db)

    def get_info(self) -> CameraInfo:
        return self._camera.get_info()

    # -----------------------------------------------------------------------
    # Compatibilità con BaseCamera — restituisce una vista "per stage"
    # -----------------------------------------------------------------------

    def as_camera(self, stage: str) -> "_StageCamera":
        """
        Ritorna un oggetto compatibile con BaseCamera per uno stage specifico.
        Utile per passarlo direttamente agli script di test esistenti.

        Esempio:
            cam_tracking = sim.as_camera("tracking")
            frame = cam_tracking.grab()
        """
        return _StageCamera(self, stage)


class _StageCamera(BaseCamera):
    """
    Adattatore: presenta il SingleCameraSimulator come una BaseCamera
    associata a un singolo stage. Non possiede la camera — la condivide.
    """

    def __init__(self, simulator: SingleCameraSimulator, stage: str) -> None:
        super().__init__(camera_id=stage)
        self._sim = simulator
        self._stage = stage

    def open(self) -> None:
        pass  # La camera è già aperta dal simulator

    def close(self) -> None:
        pass  # Non chiudiamo — la gestisce il simulator

    def grab(self, timeout_ms: int = 5000) -> Frame:
        return self._sim._grab(self._stage, timeout_ms)

    def set_exposure(self, exposure_us: float) -> None:
        self._sim.set_exposure(exposure_us)

    def set_gain(self, gain_db: float) -> None:
        self._sim.set_gain(gain_db)

    def get_info(self) -> CameraInfo:
        info = self._sim.get_info()
        info.serial = f"{info.serial}:{self._stage}"
        return info