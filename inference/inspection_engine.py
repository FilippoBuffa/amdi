"""
Engine per l'ispezione di 4 pezzi su piano.

L'immagine contiene 4 pezzi in griglia 2x2.
L'engine analizza ciascun pezzo e restituisce PASS/FAIL per ognuno.

Output: lista di 4 bool  (→ aResArray[1..4] sul PLC)
        True  = pezzo OK
        False = pezzo NG (difetto rilevato)

Stub: genera risultati con ~20% di probabilità di NG per pezzo.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import List

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class PieceResult:
    index:      int             # 1-based (1..4)
    ok:         bool            # True=OK, False=NG
    confidence: float
    defect_type: str = ""       # descrizione difetto (se NG)


@dataclass
class InspectionResult:
    pieces:       List[PieceResult]
    ok:           bool = True   # True se TUTTI e 4 i pezzi sono OK
    inference_ms: float = 0.0

    @property
    def as_bool_array(self) -> List[bool]:
        """Ordine 1..4 come richiesto dal PLC (aResArray[1..4])."""
        return [p.ok for p in sorted(self.pieces, key=lambda p: p.index)]

    @property
    def pass_count(self) -> int:
        return sum(1 for p in self.pieces if p.ok)

    @property
    def fail_count(self) -> int:
        return 4 - self.pass_count


class InspectionEngine:
    """
    Analizza 4 pezzi in griglia 2x2 sull'immagine di ispezione.

    Stub: divide l'immagine in 4 quadranti e restituisce risultati verosimili.
    """

    # Posizioni nominali dei 4 pezzi (normalizzate 0-1)
    _PIECE_CENTERS = [
        (0.25, 0.25),   # pezzo 1: in alto a sinistra
        (0.75, 0.25),   # pezzo 2: in alto a destra
        (0.25, 0.75),   # pezzo 3: in basso a sinistra
        (0.75, 0.75),   # pezzo 4: in basso a destra
    ]

    def __init__(self, model_path: str = "", ng_probability: float = 0.20) -> None:
        self._model          = None
        self._is_stub        = True
        self._ng_probability = ng_probability  # solo stub

        if model_path:
            self._load_model(model_path)

    def analyze(self, image: np.ndarray) -> InspectionResult:
        t0 = time.perf_counter()

        if self._is_stub:
            pieces = self._run_stub(image)
        else:
            pieces = self._run_model(image)

        all_ok = all(p.ok for p in pieces)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        result = InspectionResult(
            pieces=pieces,
            ok=all_ok,
            inference_ms=elapsed_ms,
        )

        log.debug(
            "InspectionEngine: %d/4 OK in %.1fms | %s",
            result.pass_count, elapsed_ms,
            [p.ok for p in pieces],
        )
        return result

    # -----------------------------------------------------------------------
    # Stub
    # -----------------------------------------------------------------------

    def _run_stub(self, image: np.ndarray) -> List[PieceResult]:
        """
        Analisi sintetica: divide in quadranti, valuta ognuno.
        Ogni pezzo ha ~ng_probability di risultare NG.
        """
        time.sleep(random.uniform(0.010, 0.040))  # simula latenza inferenza

        h, w = image.shape[:2]
        pieces = []

        for i, (cx_norm, cy_norm) in enumerate(self._PIECE_CENTERS):
            # Estrai ROI del pezzo
            cx = int(cx_norm * w)
            cy = int(cy_norm * h)
            half = min(w, h) // 6
            roi = image[
                max(0, cy - half): cy + half,
                max(0, cx - half): cx + half,
            ]

            # Analisi stub: rumore statistico
            is_ng   = random.random() < self._ng_probability
            conf    = random.uniform(0.82, 0.99)
            defect  = random.choice(["scratch", "dent", "discoloration"]) if is_ng else ""

            pieces.append(PieceResult(
                index=i + 1,
                ok=not is_ng,
                confidence=conf,
                defect_type=defect,
            ))

        return pieces

    # -----------------------------------------------------------------------
    # Reale (da implementare)
    # -----------------------------------------------------------------------

    def _load_model(self, model_path: str) -> None:
        try:
            log.info("InspectionEngine: caricamento modello da %s (TODO)", model_path)
        except Exception as exc:
            log.error("InspectionEngine: errore caricamento: %s. Uso stub.", exc)

    def _run_model(self, image: np.ndarray) -> List[PieceResult]:
        """TODO: implementa inferenza reale."""
        raise NotImplementedError("InspectionEngine reale non ancora implementato.")
