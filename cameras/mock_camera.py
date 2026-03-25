"""
Mock della telecamera per sviluppo senza hardware.

Genera immagini sintetiche realistiche per ogni tipo di stage:
  - tracking:    sfondo scuro + cerchi bianchi (i "pezzi" sul salterello)
  - orientation: pezzo singolo con orientamento variabile
  - inspection:  4 pezzi, alcuni con difetti simulati

Può anche caricare immagini da disco se fornite (per test su immagini reali).
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .base_camera import (
    BaseCamera, CameraInfo, CameraState, Frame,
    CameraTimeoutError,
)

log = logging.getLogger(__name__)


class MockCamera(BaseCamera):
    """
    Camera simulata.

    Parametro camera_id: "tracking" | "angle" | "inspection"
    Determina il tipo di immagine sintetica generata.

    Il metodo grab() simula il comportamento reale: blocca finché non arriva
    un trigger (hardware dal PLC). In modalità mock:
      - Se trigger_interval_s > 0: il trigger scatta automaticamente ogni N secondi
      - Il trigger può essere inviato manualmente con send_trigger()
        (usato dall'API Flask per test manuali)
    """

    def __init__(
        self,
        camera_id: str,
        width: int = 1024,
        height: int = 1024,
        images_dir: Optional[str] = None,
        trigger_interval_s: float = 4.0,
        timeout_probability: float = 0.0,
    ) -> None:
        super().__init__(camera_id=camera_id)

        self._width  = width
        self._height = height
        self._images_dir = Path(images_dir) if images_dir else None
        self._trigger_interval  = trigger_interval_s
        self._timeout_probability = timeout_probability

        self._state = CameraState.DISCONNECTED
        self._frame_counter = 0
        self._exposure_us = 5000.0
        self._gain_db = 0.0

        # Cache immagini da disco
        self._disk_images: list[np.ndarray] = []
        self._disk_index = 0

        # Contatore per animare le immagini sintetiche
        self._tick = 0

        # Trigger event: simulazione hardware trigger dal PLC
        # Il grab() aspetta su questo evento.
        self._trigger_event = threading.Event()
        self._auto_trigger_thread: Optional[threading.Thread] = None
        self._stop_auto = threading.Event()

    # -----------------------------------------------------------------------
    # Ciclo di vita
    # -----------------------------------------------------------------------

    def open(self) -> None:
        if self._images_dir and self._images_dir.exists():
            self._load_disk_images()
        self._state = CameraState.CONNECTED
        self._stop_auto.clear()

        if self._trigger_interval > 0:
            self._auto_trigger_thread = threading.Thread(
                target=self._auto_trigger_loop,
                daemon=True,
                name=f"mock-autotrigger-{self.camera_id}",
            )
            self._auto_trigger_thread.start()

        log.info("MockCamera [%s]: aperta (%dx%d, trigger=%.1fs)",
                 self.camera_id, self._width, self._height, self._trigger_interval)

    def close(self) -> None:
        self._stop_auto.set()
        self._trigger_event.set()  # sblocca grab() in attesa
        self._state = CameraState.DISCONNECTED
        log.info("MockCamera [%s]: chiusa.", self.camera_id)

    def send_trigger(self) -> None:
        """Trigger manuale: usabile dall'API Flask per test senza PLC."""
        log.debug("MockCamera [%s]: trigger manuale.", self.camera_id)
        self._trigger_event.set()

    def _auto_trigger_loop(self) -> None:
        while not self._stop_auto.is_set():
            self._stop_auto.wait(self._trigger_interval)
            if not self._stop_auto.is_set():
                self._trigger_event.set()

    # -----------------------------------------------------------------------
    # Acquisizione
    # -----------------------------------------------------------------------

    def grab(self, timeout_ms: int = 30_000) -> Frame:
        """
        Blocca fino all'arrivo di un trigger (hardware in produzione,
        auto/manuale nel mock). Simula il comportamento Basler reale.
        """
        timeout_s = timeout_ms / 1000.0
        triggered = self._trigger_event.wait(timeout=timeout_s)
        self._trigger_event.clear()

        if not triggered:
            raise CameraTimeoutError(
                f"MockCamera [{self.camera_id}]: timeout dopo {timeout_s:.0f}s"
            )

        if self._timeout_probability > 0 and random.random() < self._timeout_probability:
            raise CameraTimeoutError(f"MockCamera [{self.camera_id}]: timeout simulato.")

        time.sleep(random.uniform(0.005, 0.020))  # latenza acquisizione realistica

        image = self._generate_image()
        self._frame_counter += 1
        self._tick += 1

        return Frame(
            image=image,
            camera_id=self.camera_id,
            frame_id=self._frame_counter,
            timestamp=time.time(),
        )

    # -----------------------------------------------------------------------
    # Generazione immagini sintetiche
    # -----------------------------------------------------------------------

    def _generate_image(self) -> np.ndarray:
        """Dispatcha al generatore corretto in base al camera_id."""
        if self._disk_images:
            return self._next_disk_image()

        if "tracking" in self.camera_id:
            return self._gen_tracking()
        elif "orientation" in self.camera_id:
            return self._gen_orientation()
        elif "inspection" in self.camera_id:
            return self._gen_inspection()
        else:
            return self._gen_noise()

    def _gen_tracking(self) -> np.ndarray:
        """
        Sfondo scuro con N cerchi bianchi (pezzi sul salterello).
        Le posizioni variano leggermente ad ogni frame.
        """
        img = np.zeros((self._height, self._width), dtype=np.uint8)

        n_pieces = random.randint(3, 8)
        for _ in range(n_pieces):
            cx = random.randint(80, self._width - 80)
            cy = random.randint(80, self._height - 80)
            r  = random.randint(25, 45)
            brightness = random.randint(180, 255)
            cv2.circle(img, (cx, cy), r, brightness, -1)
            # Bordo più scuro per realismo
            cv2.circle(img, (cx, cy), r, max(0, brightness - 60), 2)

        # Rumore di fondo
        noise = np.random.randint(0, 15, img.shape, dtype=np.uint8)
        img = cv2.add(img, noise)
        return img

    def _gen_orientation(self) -> np.ndarray:
        """
        Singolo pezzo rettangolare con angolo casuale.
        L'angolo cambia ad ogni frame per simulare pezzi diversi.
        """
        img = np.zeros((self._height, self._width), dtype=np.uint8)
        cx, cy = self._width // 2, self._height // 2

        # Angolo che ruota nel tempo
        angle = (self._tick * 7 + random.uniform(-5, 5)) % 360

        # Rettangolo ruotato
        rect = ((cx, cy), (200, 80), angle)
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        cv2.fillPoly(img, [box], 220)
        cv2.polylines(img, [box], True, 160, 2)

        # Asimmetria: piccolo cerchio su un lato per indicare orientamento
        offset_x = int(math.cos(math.radians(angle)) * 70)
        offset_y = int(math.sin(math.radians(angle)) * 70)
        cv2.circle(img, (cx + offset_x, cy + offset_y), 10, 255, -1)

        noise = np.random.randint(0, 10, img.shape, dtype=np.uint8)
        img = cv2.add(img, noise)
        return img

    def _gen_inspection(self) -> np.ndarray:
        """
        4 pezzi in griglia 2x2.
        Alcuni hanno difetti simulati (macchie scure).
        """
        img = np.zeros((self._height, self._width), dtype=np.uint8)
        positions = [
            (self._width // 4,     self._height // 4),
            (3 * self._width // 4, self._height // 4),
            (self._width // 4,     3 * self._height // 4),
            (3 * self._width // 4, 3 * self._height // 4),
        ]

        for i, (cx, cy) in enumerate(positions):
            # Corpo pezzo
            cv2.rectangle(
                img,
                (cx - 80, cy - 80),
                (cx + 80, cy + 80),
                210, -1,
            )
            cv2.rectangle(
                img,
                (cx - 80, cy - 80),
                (cx + 80, cy + 80),
                150, 2,
            )

            # Difetto: ~20% probabilità per pezzo
            if random.random() < 0.20:
                dx = random.randint(-50, 50)
                dy = random.randint(-50, 50)
                dr = random.randint(8, 20)
                cv2.circle(img, (cx + dx, cy + dy), dr, 30, -1)   # macchia scura

        noise = np.random.randint(0, 12, img.shape, dtype=np.uint8)
        img = cv2.add(img, noise)
        return img

    def _gen_noise(self) -> np.ndarray:
        """Immagine di noise (camera generica non classificata)."""
        return np.random.randint(0, 256, (self._height, self._width), dtype=np.uint8)

    # -----------------------------------------------------------------------
    # Immagini da disco
    # -----------------------------------------------------------------------

    def _load_disk_images(self) -> None:
        extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
        files = [
            f for f in self._images_dir.iterdir()
            if f.suffix.lower() in extensions
        ]
        files.sort()
        for f in files:
            img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._disk_images.append(img)
        log.info(
            "MockCamera [%s]: caricate %d immagini da %s",
            self.camera_id, len(self._disk_images), self._images_dir,
        )

    def _next_disk_image(self) -> np.ndarray:
        img = self._disk_images[self._disk_index % len(self._disk_images)]
        self._disk_index += 1
        return img.copy()

    # -----------------------------------------------------------------------
    # Parametri (no-op nel mock, ma registrati)
    # -----------------------------------------------------------------------

    def set_exposure(self, exposure_us: float) -> None:
        self._exposure_us = exposure_us
        log.debug("MockCamera [%s]: exposure → %.0f µs", self.camera_id, exposure_us)

    def set_gain(self, gain_db: float) -> None:
        self._gain_db = gain_db
        log.debug("MockCamera [%s]: gain → %.1f dB", self.camera_id, gain_db)

    # -----------------------------------------------------------------------
    # Info
    # -----------------------------------------------------------------------

    def get_info(self) -> CameraInfo:
        return CameraInfo(
            serial=self.camera_id,
            model=f"MockCamera-{self.camera_id}",
            state=self._state,
            width=self._width,
            height=self._height,
            fps=0.0,
        )
