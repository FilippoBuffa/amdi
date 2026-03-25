"""
Engine YOLO per il tracking: individua i pezzi nell'immagine
e restituisce le coordinate del miglior candidato da prendere.

Stub: restituisce coordinate verosimili generate sinteticamente.
Quando il modello è pronto, sostituisci _run_yolo() e _select_best_pick().

Output coordinate: centesimi di mm (WORD, 0-65535)
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Detection:
    """Singolo pezzo rilevato da YOLO."""
    x_px:       float          # centro X in pixel
    y_px:       float          # centro Y in pixel
    width_px:   float          # larghezza bounding box
    height_px:  float          # altezza bounding box
    confidence: float          # score YOLO (0.0 – 1.0)
    class_id:   int   = 0


@dataclass
class TrackingResult:
    """Risultato del tracking: coordinata del pezzo scelto."""
    x_centimm:   int           # X in centesimi di mm  (→ wCoordinateX)
    y_centimm:   int           # Y in centesimi di mm  (→ wCoordinateY)
    confidence:  float
    ok:          bool = True
    detections:  List[Detection] = field(default_factory=list)
    inference_ms: float = 0.0


class YoloEngine:
    """
    Wrapper YOLO per la camera di tracking.

    In modalità stub (model_path=""):
        - Genera rilevetamenti sintetici realistici
        - Simula latenza di inferenza

    In modalità reale (model_path=<path>):
        - Carica il modello Ultralytics YOLO
        - Esegue inferenza reale
    """

    def __init__(
        self,
        model_path: str = "",
        conf_min: float = 0.7,
        px_to_centimm: float = 10.0,
        image_center_x: int = 512,
        image_center_y: int = 512,
    ) -> None:
        self._conf_min      = conf_min
        self._px_to_centimm = px_to_centimm
        self._cx            = image_center_x
        self._cy            = image_center_y
        self._model         = None
        self._is_stub       = True

        if model_path and Path(model_path).exists():
            self._load_model(model_path)
        else:
            if model_path:
                log.warning("YOLO: modello non trovato (%s). Uso stub.", model_path)
            else:
                log.info("YOLO: nessun modello configurato. Uso stub.")

    def analyze(self, image: np.ndarray) -> TrackingResult:
        """
        Analizza l'immagine e restituisce il pezzo migliore da raccogliere.

        Strategia "best pick": pezzo con confidence massima.
        (In futuro: posizione più favorevole per il robot)
        """
        t0 = time.perf_counter()

        if self._is_stub:
            detections = self._run_stub(image)
        else:
            detections = self._run_yolo(image)

        # Filtra per confidence minima
        detections = [d for d in detections if d.confidence >= self._conf_min]

        inference_ms = (time.perf_counter() - t0) * 1000

        if not detections:
            log.warning("YOLO: nessun pezzo rilevato.")
            return TrackingResult(
                x_centimm=0, y_centimm=0,
                confidence=0.0, ok=False,
                inference_ms=inference_ms,
            )

        best = self._select_best_pick(detections)
        x_cm = int(best.x_px * self._px_to_centimm)
        y_cm = int(best.y_px * self._px_to_centimm)

        # Clamp a WORD (0-65535)
        x_cm = max(0, min(65535, x_cm))
        y_cm = max(0, min(65535, y_cm))

        log.debug(
            "YOLO: best_pick px=(%.1f, %.1f) → centimm=(%d, %d) conf=%.2f in %.1fms",
            best.x_px, best.y_px, x_cm, y_cm, best.confidence, inference_ms,
        )

        return TrackingResult(
            x_centimm=x_cm,
            y_centimm=y_cm,
            confidence=best.confidence,
            ok=True,
            detections=detections,
            inference_ms=inference_ms,
        )

    # -----------------------------------------------------------------------
    # Stub
    # -----------------------------------------------------------------------

    def _run_stub(self, image: np.ndarray) -> List[Detection]:
        """Genera rilevamenti sintetici realistici."""
        # Simula latenza inferenza (5-30 ms)
        time.sleep(random.uniform(0.005, 0.030))

        h, w = image.shape[:2]
        n = random.randint(2, 7)
        detections = []

        for _ in range(n):
            detections.append(Detection(
                x_px=random.uniform(w * 0.1, w * 0.9),
                y_px=random.uniform(h * 0.1, h * 0.9),
                width_px=random.uniform(40, 90),
                height_px=random.uniform(40, 90),
                confidence=random.uniform(0.65, 0.99),
            ))

        return detections

    def _select_best_pick(self, detections: List[Detection]) -> Detection:
        """
        Seleziona il pezzo migliore da raccogliere.
        Criterio attuale: massima confidence.
        TODO: potrebbe considerare posizione relativa al robot, etc.
        """
        return max(detections, key=lambda d: d.confidence)

    # -----------------------------------------------------------------------
    # Inferenza reale (da riempire quando il modello è pronto)
    # -----------------------------------------------------------------------

    def _load_model(self, model_path: str) -> None:
        try:
            from ultralytics import YOLO
            self._model  = YOLO(model_path)
            self._is_stub = False
            log.info("YOLO: modello caricato da %s", model_path)
        except Exception as exc:
            log.error("YOLO: errore caricamento modello: %s. Uso stub.", exc)
            self._is_stub = True

    def _run_yolo(self, image: np.ndarray) -> List[Detection]:
        """Inferenza reale con Ultralytics YOLO."""
        results = self._model(image, conf=self._conf_min, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(Detection(
                    x_px=(x1 + x2) / 2,
                    y_px=(y1 + y2) / 2,
                    width_px=x2 - x1,
                    height_px=y2 - y1,
                    confidence=float(box.conf[0]),
                    class_id=int(box.cls[0]),
                ))
        return detections
