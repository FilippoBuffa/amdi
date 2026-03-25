"""
Configurazione centrale del progetto.
Tutti i parametri modificabili dall'esterno tramite variabili d'ambiente
o file .env. I valori di default sono pensati per sviluppo locale.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage"))
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "db" / "machine.db"))

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
@dataclass
class FlaskConfig:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FLASK_PORT", 5000))


# ---------------------------------------------------------------------------
# PLC / ADS
# ---------------------------------------------------------------------------
@dataclass
class ADSConfig:
    # Indirizzo AMS del PLC TwinCAT 3 (formato: "x.x.x.x.1.1")
    PLC_AMS_NET_ID: str = os.getenv("PLC_AMS_NET_ID", "5.80.201.232.1.1")
    # Porta ADS (851 = TwinCAT 3 runtime 1)
    PLC_PORT: int = int(os.getenv("PLC_PORT", 851))
    # Timeout connessione in secondi
    CONNECT_TIMEOUT: float = float(os.getenv("ADS_CONNECT_TIMEOUT", 5.0))
    # Intervallo polling variabili PLC (ms)
    POLL_INTERVAL_MS: int = int(os.getenv("ADS_POLL_INTERVAL_MS", 10))

    # --- Nomi variabili TwinCAT (da adattare al progetto PLC) ---
    # Trigger: il PLC scrive TRUE per indicare che la foto è pronta
    VAR_TRIGGER_TRACKING:    str = "MAIN.bTriggerTracking"
    VAR_TRIGGER_ORIENTATION: str = "MAIN.bTriggerOrientation"
    VAR_TRIGGER_INSPECTION:  str = "MAIN.bTriggerInspection"

    # Risultati che il backend scrive sul PLC
    VAR_RESULT_TRACKING_X:   str = "MAIN.fTrackingX"
    VAR_RESULT_TRACKING_Y:   str = "MAIN.fTrackingY"
    VAR_RESULT_TRACKING_OK:  str = "MAIN.bTrackingOK"

    VAR_RESULT_ANGLE:        str = "MAIN.fOrientationAngle"
    VAR_RESULT_ORIENTATION_OK: str = "MAIN.bOrientationOK"

    # Array di 4 risultati ispezione (BOOL[0..3])
    VAR_RESULT_INSPECTION:   str = "MAIN.bInspectionResults"
    VAR_RESULT_INSPECTION_OK: str = "MAIN.bInspectionDone"

    # Stato macchina letto dal PLC
    VAR_MACHINE_RUNNING:     str = "MAIN.bMachineRunning"
    VAR_MACHINE_ERROR:       str = "MAIN.bMachineError"


# ---------------------------------------------------------------------------
# Telecamere Basler
# ---------------------------------------------------------------------------
@dataclass
class CameraConfig:
    # Serial number o "MOCK" per usare il mock
    SERIAL_TRACKING:    str = os.getenv("CAM_SERIAL_TRACKING",    "MOCK")
    SERIAL_ORIENTATION: str = os.getenv("CAM_SERIAL_ORIENTATION", "MOCK")
    SERIAL_INSPECTION:  str = os.getenv("CAM_SERIAL_INSPECTION",  "MOCK")

    # Parametri comuni acquisizione
    EXPOSURE_TIME_US: float = float(os.getenv("CAM_EXPOSURE_US", 5000.0))
    GAIN_DB:          float = float(os.getenv("CAM_GAIN_DB", 0.0))

    # Risoluzione attesa (per validazione)
    EXPECTED_WIDTH:  int = int(os.getenv("CAM_WIDTH",  2048))
    EXPECTED_HEIGHT: int = int(os.getenv("CAM_HEIGHT", 2048))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
@dataclass
class PipelineConfig:
    # Quanti pezzi si accumulano prima di lanciare l'ispezione
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", 4))

    # Timeout (secondi) oltre cui un pezzo "in volo" nella pipeline viene scartato
    PIECE_TIMEOUT_S: float = float(os.getenv("PIECE_TIMEOUT_S", 30.0))

    # Quanti pezzi/batch tenere in memoria (ring buffer per HMI)
    HISTORY_BUFFER_SIZE: int = int(os.getenv("HISTORY_BUFFER_SIZE", 200))


# ---------------------------------------------------------------------------
# Storage immagini
# ---------------------------------------------------------------------------
@dataclass
class StorageConfig:
    ROOT: Path = STORAGE_DIR / "images"

    # Sottocartelle per ogni stage
    TRACKING_DIR:    Path = ROOT / "tracking"
    ORIENTATION_DIR: Path = ROOT / "orientation"
    INSPECTION_DIR:  Path = ROOT / "inspection"

    # Formato data per suddivisione giornaliera  YYYY-MM-DD
    DATE_FORMAT: str = "%Y-%m-%d"

    # Qualità JPEG per il salvataggio (0-100)
    JPEG_QUALITY: int = int(os.getenv("STORAGE_JPEG_QUALITY", 90))

    # Abilita copia asincrona su remote folder
    REMOTE_ENABLED: bool = os.getenv("REMOTE_ENABLED", "false").lower() == "true"
    REMOTE_ROOT: Path = Path(os.getenv("REMOTE_ROOT", r"\\server\qc_images"))


# ---------------------------------------------------------------------------
# Algoritmi Vision (soglie, parametri — da rifinire per ogni applicazione)
# ---------------------------------------------------------------------------
@dataclass
class VisionConfig:
    # Tracking
    TRACKING_MIN_AREA:        int   = int(os.getenv("TRACKING_MIN_AREA", 500))
    TRACKING_MAX_AREA:        int   = int(os.getenv("TRACKING_MAX_AREA", 50000))
    TRACKING_CONFIDENCE_MIN:  float = float(os.getenv("TRACKING_CONF_MIN", 0.7))

    # Orientation
    ORIENTATION_METHOD: str = os.getenv("ORIENTATION_METHOD", "hough")  # hough | template

    # Inspection
    INSPECTION_THRESHOLD: float = float(os.getenv("INSPECTION_THRESHOLD", 0.85))
    INSPECTION_MODEL_PATH: str  = os.getenv("INSPECTION_MODEL_PATH", "")


# ---------------------------------------------------------------------------
# Istanze globali (singleton semplice, importabili ovunque)
# ---------------------------------------------------------------------------
flask_cfg    = FlaskConfig()
ads_cfg      = ADSConfig()
camera_cfg   = CameraConfig()
pipeline_cfg = PipelineConfig()
storage_cfg  = StorageConfig()
vision_cfg   = VisionConfig()


def ensure_dirs() -> None:
    """Crea tutte le directory necessarie se non esistono."""
    for d in [
        storage_cfg.TRACKING_DIR,
        storage_cfg.ORIENTATION_DIR,
        storage_cfg.INSPECTION_DIR,
        DB_PATH.parent,
    ]:
        d.mkdir(parents=True, exist_ok=True)
