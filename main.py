"""
Punto di ingresso AmdiApp.

Avvia:
  1. Logging
  2. Orchestratore (PLC + 3 worker camera)
  3. Flask API

Uso:
    python main.py
    ADS_USE_MOCK=false python main.py   # PLC reale
"""

from __future__ import annotations

import logging
import signal
import sys
import os

# Carica .env PRIMA di tutto
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Aggiungi il parent directory al path per imports relativi
sys.path.insert(0, os.path.dirname(__file__))


def setup_logging() -> None:
    from config import log_cfg
    level = getattr(logging, log_cfg.LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silenzia librerie verbose
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    log = logging.getLogger("main")

    log.info("=" * 60)
    log.info("  AmdiApp Backend — avvio")
    log.info("=" * 60)

    from config import flask_cfg, ads_cfg
    from core.orchestrator import Orchestrator
    from api.app import create_app

    # Avvia orchestratore
    orch = Orchestrator()
    orch.start()

    # Gestione SIGINT / SIGTERM
    def _shutdown(sig, frame):
        log.info("Segnale %d ricevuto — shutdown...", sig)
        orch.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Avvia Flask
    app = create_app(orch)
    log.info("Flask in ascolto su http://%s:%d", flask_cfg.HOST, flask_cfg.PORT)
    app.run(
        host=flask_cfg.HOST,
        port=flask_cfg.PORT,
        debug=flask_cfg.DEBUG,
        use_reloader=False,   # reloader incompatibile con thread background
        threaded=True,
    )


if __name__ == "__main__":
    main()
