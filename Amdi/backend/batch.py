"""
Modello che rappresenta un batch di 4 pezzi ispezionati insieme da CAM3.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from piece import InspectionResult


@dataclass
class Batch:
    # --- Identità ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    # --- Contenuto ---
    piece_ids: List[str] = field(default_factory=list)           # 4 id di Piece
    results: List[Optional[InspectionResult]] = field(default_factory=list)  # 4 risultati

    # --- Immagine condivisa del batch ---
    image_path: Optional[str] = None
    inspection_ts: Optional[datetime] = None

    # --- Stato ---
    completed: bool = False

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self.piece_ids)

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r == InspectionResult.OK)

    @property
    def ng_count(self) -> int:
        return sum(1 for r in self.results if r == InspectionResult.NG)

    @property
    def all_ok(self) -> bool:
        return self.completed and self.ng_count == 0

    def complete(
        self,
        results: List[InspectionResult],
        image_path: Optional[str] = None,
    ) -> None:
        """Chiude il batch con i risultati dell'ispezione."""
        self.results = results
        self.image_path = image_path
        self.inspection_ts = datetime.utcnow()
        self.completed = True

    # -----------------------------------------------------------------------
    # Serializzazione
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "completed": self.completed,
            "size": self.size,
            "piece_ids": self.piece_ids,
            "results": [r.value if r else None for r in self.results],
            "ok_count": self.ok_count,
            "ng_count": self.ng_count,
            "all_ok": self.all_ok,
            "image_path": self.image_path,
            "inspection_ts": self.inspection_ts.isoformat() if self.inspection_ts else None,
        }