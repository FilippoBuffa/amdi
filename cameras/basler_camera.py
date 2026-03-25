"""
Wrapper per telecamere Basler GigE via pypylon.
Modalità hardware trigger: il PLC triggera ogni acquisizione via EPP2008.
Grabbing continuo: StartGrabbing una volta all'open, RetrieveResult ad ogni grab.
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

from .base_camera import (
    BaseCamera, CameraInfo, CameraState, Frame,
    CameraError, CameraTimeoutError, CameraConnectionError,
)

log = logging.getLogger(__name__)


class BaslerCamera(BaseCamera):
    """
    Telecamera Basler GigE con hardware trigger via pypylon.

    Il PLC triggera ogni frame tramite l'uscita digitale EPP2008.
    Grabbing continuo: aperto in open(), chiuso in close().

    Uso:
        cam = BaslerCamera(camera_id="tracking", serial="40724552")
        cam.open()
        frame = cam.grab(timeout_ms=60_000)   # blocca fino al trigger HW
        cam.close()
    """

    def __init__(
        self,
        camera_id: str,
        serial: Optional[str] = None,
        ip: Optional[str] = None,
        exposure_us: float = 10_000.0,
        gain_db: float = 0.0,
        trigger_source: str = "Line3",          # Line3 = opto input su ace2 GigE
        trigger_activation: str = "RisingEdge",
    ) -> None:
        super().__init__(camera_id=camera_id)

        if not serial and not ip:
            raise ValueError("Specificare serial= oppure ip=")

        if not PYPYLON_AVAILABLE:
            raise CameraConnectionError(
                "pypylon non installato. Installa con: pip install pypylon"
            )

        self._serial            = serial
        self._ip                = ip
        self._exposure_us       = exposure_us
        self._gain_db           = gain_db
        self._trigger_source    = trigger_source
        self._trigger_activation = trigger_activation

        self._camera: Optional[pylon.InstantCamera] = None
        self._state         = CameraState.DISCONNECTED
        self._frame_counter = 0
        self._grabbing      = False

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

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
                device  = None
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

            # Avvia grabbing continuo — i frame arrivano solo al trigger HW
            self._camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
            self._grabbing = True
            self._state    = CameraState.CONNECTED

            info = self._camera.GetDeviceInfo()
            log.info(
                "Basler [%s]: connessa. Model=%s Serial=%s  trigger=%s/%s",
                self.camera_id,
                info.GetModelName(),
                info.GetSerialNumber(),
                self._trigger_source,
                self._trigger_activation,
            )

        except CameraConnectionError:
            raise
        except Exception as exc:
            self._state = CameraState.ERROR
            raise CameraConnectionError(
                f"Errore apertura camera [{self.camera_id}]: {exc}"
            ) from exc

    def close(self) -> None:
        if self._camera:
            try:
                if self._grabbing:
                    self._camera.StopGrabbing()
                    self._grabbing = False
                if self._camera.IsOpen():
                    self._camera.Close()
            except Exception as exc:
                log.warning("Basler [%s]: errore chiusura: %s", self.camera_id, exc)
        self._state = CameraState.DISCONNECTED
        log.info("Basler [%s]: chiusa.", self.camera_id)

    # -----------------------------------------------------------------------
    # Acquisizione
    # -----------------------------------------------------------------------

    def grab(self, timeout_ms: int = 60_000) -> Frame:
        """
        Attende il prossimo frame triggerato dal PLC.
        Blocca fino a timeout_ms millisecondi.
        """
        if not self._camera or not self._camera.IsOpen():
            raise CameraConnectionError(f"Camera [{self.camera_id}] non aperta.")
        if not self._grabbing:
            raise CameraConnectionError(f"Camera [{self.camera_id}] grabbing non attivo.")

        self._state = CameraState.GRABBING
        try:
            with self._camera.RetrieveResult(
                timeout_ms, pylon.TimeoutHandling_ThrowException
            ) as result:
                if not result.GrabSucceeded():
                    raise CameraError(
                        f"Grab fallito [{self.camera_id}]: {result.GetErrorDescription()}"
                    )
                image = result.Array.copy()

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
                f"Timeout grab [{self.camera_id}] ({timeout_ms}ms) — nessun trigger ricevuto"
            ) from exc
        except (CameraError, CameraConnectionError):
            self._state = CameraState.ERROR
            raise
        except Exception as exc:
            self._state = CameraState.ERROR
            raise CameraError(f"Errore grab [{self.camera_id}]: {exc}") from exc

    def abort_grab(self) -> None:
        """Sblocca un grab() in attesa (chiamato da _on_stop_requested)."""
        if self._camera and self._grabbing:
            try:
                self._camera.StopGrabbing()
                self._grabbing = False
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Setters
    # -----------------------------------------------------------------------

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
        )

    # -----------------------------------------------------------------------
    # Configurazione interna
    # -----------------------------------------------------------------------

    def _configure(self) -> None:
        cam = self._camera

        # Formato immagine — full resolution, Mono8
        cam.Width.SetValue(cam.Width.GetMax())
        cam.Height.SetValue(cam.Height.GetMax())
        cam.OffsetX.SetValue(0)
        cam.OffsetY.SetValue(0)
        cam.PixelFormat.SetValue("Mono8")

        # Esposizione e gain manuali
        cam.ExposureAuto.SetValue("Off")
        cam.ExposureTime.SetValue(self._exposure_us)
        cam.GainAuto.SetValue("Off")
        cam.Gain.SetValue(self._gain_db)

        # Hardware trigger dal PLC (EPP2008 → opto input camera)
        cam.TriggerSelector.SetValue("FrameStart")
        cam.TriggerMode.SetValue("On")
        cam.TriggerSource.SetValue(self._trigger_source)
        cam.TriggerActivation.SetValue(self._trigger_activation)

        # Frame rate libero (comandato dal trigger, non da timer interno)
        try:
            cam.AcquisitionFrameRateEnable.SetValue(False)
        except Exception:
            pass

        log.debug(
            "Basler [%s]: configurata — %dx%d Mono8 exp=%.0fus gain=%.1fdB trig=%s/%s",
            self.camera_id,
            cam.Width.GetValue(), cam.Height.GetValue(),
            self._exposure_us, self._gain_db,
            self._trigger_source, self._trigger_activation,
        )
