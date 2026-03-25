"""
Modello che rappresenta un singolo pezzo nella pipeline di controllo qualità.
Viaggia attraverso i 3 stage: Tracking → Orientation → Inspection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PieceStage(str, Enum):
    """Stage corrente del pezzo nella pipeline."""
    CREATED     = "created"      # creato, in attesa di tracking
    TRACKED     = "tracked"      # posizione acquisita
    ORIENTED    = "oriented"     # angolo acquisito
    IN_BATCH    = "in_batch"     # inserito in un batch, in attesa ispezione
    INSPECTED   = "inspected"    # ispezione completata
    TIMEOUT     = "timeout"      # scartato per timeout
    ERROR       = "error"        # errore in uno degli stage


class InspectionResult(str, Enum):
    OK = "OK"
    NG = "NG"


@dataclass
class Piece:
    # --- Identità ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    stage: PieceStage = PieceStage.CREATED

    # --- Stage 1: Tracking ---
    tracking_x: Optional[float] = None
    tracking_y: Optional[float] = None
    tracking_image_path: Optional[str] = None
    tracking_ts: Optional[datetime] = None

    # --- Stage 2: Orientation ---
    orientation_angle: Optional[float] = None
    orientation_image_path: Optional[str] = None
    orientation_ts: Optional[datetime] = None

    # --- Stage 3: Inspection ---
    batch_id: Optional[str] = None
    inspection_result: Optional[InspectionResult] = None
    inspection_image_path: Optional[str] = None   # condivisa con gli altri pezzi del batch
    inspection_ts: Optional[datetime] = None

    # --- Errori ---
    error_stage: Optional[str] = None
    error_message: Optional[str] = None

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def set_tracking(
        self,
        x: float,
        y: float,
        image_path: Optional[str] = None,
    ) -> None:
        self.tracking_x = x
        self.tracking_y = y
        self.tracking_image_path = image_path
        self.tracking_ts = datetime.utcnow()
        self.stage = PieceStage.TRACKED

    def set_orientation(
        self,
        angle: float,
        image_path: Optional[str] = None,
    ) -> None:
        self.orientation_angle = angle
        self.orientation_image_path = image_path
        self.orientation_ts = datetime.utcnow()
        self.stage = PieceStage.ORIENTED

    def set_inspection(
        self,
        result: InspectionResult,
        batch_id: str,
        image_path: Optional[str] = None,
    ) -> None:
        self.inspection_result = result
        self.batch_id = batch_id
        self.inspection_image_path = image_path
        self.inspection_ts = datetime.utcnow()
        self.stage = PieceStage.INSPECTED

    def mark_error(self, stage: str, message: str) -> None:
        self.error_stage = stage
        self.error_message = message
        self.stage = PieceStage.ERROR

    def mark_timeout(self) -> None:
        self.stage = PieceStage.TIMEOUT

    # -----------------------------------------------------------------------
    # Serializzazione per WebSocket / REST
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "stage": self.stage.value,
            "tracking": {
                "x": self.tracking_x,
                "y": self.tracking_y,
                "image_path": self.tracking_image_path,
                "ts": self.tracking_ts.isoformat() if self.tracking_ts else None,
            },
            "orientation": {
                "angle": self.orientation_angle,
                "image_path": self.orientation_image_path,
                "ts": self.orientation_ts.isoformat() if self.orientation_ts else None,
            },
            "inspection": {
                "result": self.inspection_result.value if self.inspection_result else None,
                "batch_id": self.batch_id,
                "image_path": self.inspection_image_path,
                "ts": self.inspection_ts.isoformat() if self.inspection_ts else None,
            },
            "error": {
                "stage": self.error_stage,
                "message": self.error_message,
            } if self.error_stage else None,
        }
