"""
Engine per la stima dell'angolo del pezzo (camera angolo).

Output: intero 0-359 gradi  (→ iCoordinateA, tipo BYTE sul PLC)

Stub: restituisce angolo verosimile.
In produzione: sostituisci _run_model() con il tuo algoritmo / rete.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class AngleResult:
    angle_deg:    int           # angolo 0-359  (→ iCoordinateA)
    confidence:   float
    ok:           bool = True
    inference_ms: float = 0.0


class AngleEngine:
    """
    Stima l'orientamento angolare del pezzo.

    Stub: simula latenza e restituisce angolo casuale realistico.
    """

    def __init__(self, model_path: str = "") -> None:
        self._model    = None
        self._is_stub  = True

        if model_path:
            self._load_model(model_path)

    def analyze(self, image: np.ndarray) -> AngleResult:
        t0 = time.perf_counter()

        if self._is_stub:
            result = self._run_stub(image)
        else:
            result = self._run_model(image)

        result.inference_ms = (time.perf_counter() - t0) * 1000
        log.debug("AngleEngine: %d° (conf=%.2f) in %.1fms",
                  result.angle_deg, result.confidence, result.inference_ms)
        return result

    # -----------------------------------------------------------------------
    # Stub
    # -----------------------------------------------------------------------

    def _run_stub(self, image: np.ndarray) -> AngleResult:
        time.sleep(random.uniform(0.005, 0.020))
        angle = random.randint(0, 359)
        return AngleResult(
            angle_deg=angle,
            confidence=random.uniform(0.80, 0.99),
            ok=True,
        )

    # -----------------------------------------------------------------------
    # Reale (da implementare)
    # -----------------------------------------------------------------------

    def _load_model(self, model_path: str) -> None:
        try:
            # TODO: carica il tuo modello (es. torchvision, ONNX, etc.)
            log.info("AngleEngine: caricamento modello da %s (TODO)", model_path)
        except Exception as exc:
            log.error("AngleEngine: errore caricamento: %s. Uso stub.", exc)

    def _run_model(self, image: np.ndarray) -> AngleResult:
        """
        TODO: implementa inferenza reale.
        Deve restituire AngleResult con angle_deg e confidence.
        """
        raise NotImplementedError("AngleEngine reale non ancora implementato.")
