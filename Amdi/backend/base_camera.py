"""
Interfaccia astratta per le telecamere.
Basler reale e mock implementano questa classe.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class CameraState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED    = "connected"
    GRABBING     = "grabbing"
    ERROR        = "error"


@dataclass
class CameraInfo:
    serial:     str
    model:      str
    state:      CameraState
    width:      int = 0
    height:     int = 0
    fps:        float = 0.0
    error_msg:  Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "serial":    self.serial,
            "model":     self.model,
            "state":     self.state.value,
            "width":     self.width,
            "height":    self.height,
            "fps":       self.fps,
            "error_msg": self.error_msg,
        }


@dataclass
class Frame:
    """Un frame acquisito dalla telecamera."""
    image:      np.ndarray                      # array HxW o HxWxC
    camera_id:  str                             # serial o nome logico
    frame_id:   int     = 0
    timestamp:  float   = 0.0                   # secondi epoch
    width:      int     = field(init=False)
    height:     int     = field(init=False)

    def __post_init__(self):
        self.height, self.width = self.image.shape[:2]

    @property
    def is_color(self) -> bool:
        return self.image.ndim == 3

    @property
    def is_gray(self) -> bool:
        return self.image.ndim == 2


class BaseCamera(ABC):
    """
    Interfaccia comune per tutte le telecamere.

    Uso tipico:
        cam = BaslerCamera("serial123")   # o MockCamera("tracking")
        cam.open()
        frame = cam.grab()
        cam.close()
    """

    def __init__(self, camera_id: str) -> None:
        self.camera_id = camera_id

    @abstractmethod
    def open(self) -> None:
        """Apre la connessione alla camera."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Chiude la connessione."""
        ...

    @abstractmethod
    def grab(self, timeout_ms: int = 5000) -> Frame:
        """
        Acquisisce un singolo frame.
        Blocca fino a timeout_ms millisecondi.
        Lancia CameraTimeoutError se nessun frame arriva in tempo.
        """
        ...

    @abstractmethod
    def get_info(self) -> CameraInfo:
        """Ritorna le info correnti della camera."""
        ...

    @abstractmethod
    def set_exposure(self, exposure_us: float) -> None:
        ...

    @abstractmethod
    def set_gain(self, gain_db: float) -> None:
        ...

    # Context manager support
    def __enter__(self) -> "BaseCamera":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()


# Eccezioni specifiche
class CameraError(Exception):
    pass

class CameraTimeoutError(CameraError):
    pass

class CameraConnectionError(CameraError):
    pass
