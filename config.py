"""
Configurazione centrale AmdiApp.
Tutti i parametri sono override-abili da variabili d'ambiente o file .env.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
@dataclass
class FlaskConfig:
    HOST:       str  = os.getenv("FLASK_HOST",  "0.0.0.0")
    PORT:       int  = int(os.getenv("FLASK_PORT", 5000))
    DEBUG:      bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    SECRET_KEY: str  = os.getenv("SECRET_KEY",  "amdi-dev-secret")


# ---------------------------------------------------------------------------
# PLC / ADS
# ---------------------------------------------------------------------------
@dataclass
class ADSConfig:
    AMS_NET_ID:      str   = os.getenv("PLC_AMS_NET_ID", "5.80.201.232.1.1")
    PORT:            int   = int(os.getenv("PLC_PORT", 851))
    POLL_INTERVAL_MS: int  = int(os.getenv("ADS_POLL_MS", 50))   # ms tra letture handshake
    CONNECT_TIMEOUT:  float = float(os.getenv("ADS_CONNECT_TIMEOUT", 5.0))
    USE_MOCK:        bool  = os.getenv("ADS_USE_MOCK", "true").lower() == "true"
    PLC_IP      = os.getenv("PLC_IP", "192.168.0.11")
    PLC_LOCAL_AMS = os.getenv("PLC_LOCAL_AMS", "192.168.0.1.1.1")

    # Handshake: timeout massimo in secondi prima di considerare il PLC silenzioso
    HANDSHAKE_TIMEOUT_S: float = float(os.getenv("ADS_HANDSHAKE_TIMEOUT", 10.0))

    # Mock: dopo quanti secondi il mock simula che il PLC ha letto (reset flag)
    MOCK_PLC_READ_DELAY_S: float = float(os.getenv("MOCK_PLC_READ_DELAY", 1.5))


# ---------------------------------------------------------------------------
# Telecamere
# ---------------------------------------------------------------------------
@dataclass
class CameraConfig:
    # True = connetti le telecamere Basler reali via IP statico
    # False (default) = usa MockCamera (utile in sviluppo senza hardware)
    USE_REAL_CAMERAS: bool = os.getenv("CAM_USE_REAL", "false").lower() == "true"

    # IP statici telecamere (usati quando USE_REAL_CAMERAS=true)
    IP_TRACKING:    str = os.getenv("CAM_IP_TRACKING",   "10.10.90.10")
    IP_ANGLE:       str = os.getenv("CAM_IP_ANGLE",      "10.10.90.11")
    IP_INSPECTION:  str = os.getenv("CAM_IP_INSPECTION", "10.10.90.12")

    EXPOSURE_US: float = float(os.getenv("CAM_EXPOSURE_US", 5000.0))
    GAIN_DB:     float = float(os.getenv("CAM_GAIN_DB", 0.0))

    # Mock: simula un nuovo trigger ogni N secondi (0 = manuale via Flask)
    MOCK_TRIGGER_INTERVAL_S: float = float(os.getenv("MOCK_TRIGGER_INTERVAL", 4.0))


# ---------------------------------------------------------------------------
# Inference / Vision
# ---------------------------------------------------------------------------
@dataclass
class VisionConfig:
    # Path modello YOLO per tracking (stub se non esiste)
    YOLO_MODEL_PATH: str  = os.getenv("YOLO_MODEL_PATH", "")
    YOLO_CONF_MIN:   float = float(os.getenv("YOLO_CONF_MIN", 0.7))

    # Modello angolo
    ANGLE_MODEL_PATH: str = os.getenv("ANGLE_MODEL_PATH", "")

    # Modello ispezione
    INSPECTION_MODEL_PATH: str = os.getenv("INSPECTION_MODEL_PATH", "")

    # Coordinate di riferimento centro immagine (mm, centesimi)
    IMAGE_CENTER_X_PX: int = int(os.getenv("IMAGE_CENTER_X_PX", 1024))
    IMAGE_CENTER_Y_PX: int = int(os.getenv("IMAGE_CENTER_Y_PX", 1024))

    # Scala pixel → centesimi di mm  (es: 1 pixel = 10 centesimi di mm → scale=10)
    PX_TO_CENTIMM_SCALE: float = float(os.getenv("PX_TO_CENTIMM", 10.0))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
@dataclass
class LogConfig:
    LEVEL:      str = os.getenv("LOG_LEVEL", "INFO")
    MAX_EVENTS: int = int(os.getenv("LOG_MAX_EVENTS", 500))   # eventi in-memory per HMI


# ---------------------------------------------------------------------------
# Istanze globali
# ---------------------------------------------------------------------------
flask_cfg  = FlaskConfig()
ads_cfg    = ADSConfig()
cam_cfg    = CameraConfig()
vision_cfg = VisionConfig()
log_cfg    = LogConfig()
