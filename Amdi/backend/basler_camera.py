"""
Wrapper per telecamere Basler GigE via pypylon.
Supporta connessione per IP (GigE) o per serial number.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np

try:
    from pypylon import pylon
    PYPYLON_AVAILABLE = True
except ImportError:
    PYPYLON_AVAILABLE = False

from base_camera import (
    BaseCamera, CameraInfo, CameraState, Frame,
    CameraError, CameraTimeoutError, CameraConnectionError,
)

log = logging.getLogger(__name__)


class BaslerCamera(BaseCamera):
    """
    Telecamera Basler GigE via pypylon.

    Connessione per IP:     BaslerCamera(camera_id="tracking", ip="192.168.1.2")
    Connessione per serial: BaslerCamera(camera_id="tracking", serial="12345678")
    """

    def __init__(
        self,
        camera_id: str,
        ip: Optional[str] = None,
        serial: Optional[str] = None,
        exposure_us: float = 10000.0,
        gain_db: float = 0.0,
        fps: float = 10.0,
    ) -> None:
        super().__init__(camera_id=camera_id)

        if not ip and not serial:
            raise ValueError("Specificare ip= oppure serial=")

        if not PYPYLON_AVAILABLE:
            raise CameraConnectionError(
                "pypylon non installato. Installa con: pip install pypylon"
            )

        self._ip = ip
        self._serial = serial
        self._exposure_us = exposure_us
        self._gain_db = gain_db
        self._fps = fps

        self._camera: Optional[pylon.InstantCamera] = None
        self._state = CameraState.DISCONNECTED
        self._frame_counter = 0

    def open(self) -> None:
        log.info("Basler [%s]: connessione in corso...", self.camera_id)
        try:
            factory = pylon.TlFactory.GetInstance()

            if self._ip:
                info = pylon.DeviceInfo()
                info.SetIpAddress(self._ip)
                device = factory.CreateDevice(info)
            else:
                devices = factory.EnumerateDevices()
                device = None
                for dev in devices:
                    if dev.GetSerialNumber() == self._serial:
                        device = factory.CreateDevice(dev)
                        break
                if device is None:
                    available = [d.GetSerialNumber() for d in devices]
                    raise CameraConnectionError(
                        f"Serial '{self._serial}' non trovato. Disponibili: {available}"
                    )

            self._camera = pylon.InstantCamera(device)
            self._camera.Open()
            self._configure()
            self._state = CameraState.CONNECTED

            info = self._camera.GetDeviceInfo()
            log.info(
                "Basler [%s]: connessa. Modello=%s Serial=%s IP=%s",
                self.camera_id,
                info.GetModelName(),
                info.GetSerialNumber(),
                self._ip or "N/A",
            )

        except CameraConnectionError:
            raise
        except Exception as exc:
            self._state = CameraState.ERROR
            raise CameraConnectionError(
                f"Errore apertura camera [{self.camera_id}]: {exc}"
            ) from exc

    def close(self) -> None:
        if self._camera and self._camera.IsOpen():
            try:
                if self._camera.IsGrabbing():
                    self._camera.StopGrabbing()
                self._camera.Close()
            except Exception as exc:
                log.warning("Basler [%s]: errore chiusura: %s", self.camera_id, exc)
        self._state = CameraState.DISCONNECTED
        log.info("Basler [%s]: chiusa.", self.camera_id)

    def grab(self, timeout_ms: int = 5000) -> Frame:
        if not self._camera or not self._camera.IsOpen():
            raise CameraConnectionError(f"Camera [{self.camera_id}] non aperta.")

        self._state = CameraState.GRABBING
        try:
            self._camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

            with self._camera.RetrieveResult(
                timeout_ms, pylon.TimeoutHandling_ThrowException
            ) as result:
                if not result.GrabSucceeded():
                    raise CameraError(
                        f"Grab fallito [{self.camera_id}]: {result.GetErrorDescription()}"
                    )
                image = result.Array.copy()

            self._camera.StopGrabbing()
            self._frame_counter += 1
            self._state = CameraState.CONNECTED

            return Frame(
                image=image,
                camera_id=self.camera_id,
                frame_id=self._frame_counter,
                timestamp=time.time(),
            )

        except pylon.TimeoutException as exc:
            self._state = CameraState.CONNECTED
            raise CameraTimeoutError(
                f"Timeout grab [{self.camera_id}] ({timeout_ms}ms)"
            ) from exc
        except (CameraError, CameraConnectionError):
            self._state = CameraState.ERROR
            raise
        except Exception as exc:
            self._state = CameraState.ERROR
            raise CameraError(f"Errore grab [{self.camera_id}]: {exc}") from exc

    def set_exposure(self, exposure_us: float) -> None:
        self._exposure_us = exposure_us
        if self._camera and self._camera.IsOpen():
            self._camera.ExposureTime.SetValue(exposure_us)

    def set_gain(self, gain_db: float) -> None:
        self._gain_db = gain_db
        if self._camera and self._camera.IsOpen():
            self._camera.Gain.SetValue(gain_db)

    def get_info(self) -> CameraInfo:
        if not self._camera or not self._camera.IsOpen():
            return CameraInfo(
                serial=self._serial or self._ip or "?",
                model="unknown",
                state=self._state,
            )
        dev = self._camera.GetDeviceInfo()
        return CameraInfo(
            serial=dev.GetSerialNumber(),
            model=dev.GetModelName(),
            state=self._state,
            width=self._camera.Width.GetValue(),
            height=self._camera.Height.GetValue(),
            fps=self._fps,
        )

    def _configure(self) -> None:
        cam = self._camera
        cam.Width.SetValue(cam.Width.GetMax())
        cam.Height.SetValue(cam.Height.GetMax())
        cam.OffsetX.SetValue(0)
        cam.OffsetY.SetValue(0)
        cam.PixelFormat.SetValue("Mono8")
        cam.ExposureAuto.SetValue("Off")
        cam.ExposureTime.SetValue(self._exposure_us)
        cam.GainAuto.SetValue("Off")
        cam.Gain.SetValue(self._gain_db)
        cam.AcquisitionFrameRateEnable.SetValue(True)
        cam.AcquisitionFrameRate.SetValue(self._fps)
        cam.TriggerMode.SetValue("Off")