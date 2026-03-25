"""
Factory: restituisce il client ADS corretto (reale o mock)
in base alla variabile ADS_MODE nella config.

Uso:
    from core.plc import create_ads_client
    client = create_ads_client()
    client.start()
"""

from __future__ import annotations

import os
import logging

from .base_ads_client import BaseADSClient
from .mock_ads_client import MockADSClient

# ADSClient richiede pyads — importato solo se disponibile
try:
    from .ads_client import ADSClient
except ImportError:
    ADSClient = None  # type: ignore

log = logging.getLogger(__name__)


def create_ads_client() -> BaseADSClient:
    """
    Istanzia il client ADS in base alla variabile d'ambiente ADS_MODE.

    ADS_MODE=real  → ADSClient (richiede TwinCAT3 raggiungibile)
    ADS_MODE=mock  → MockADSClient (default, nessun hardware necessario)
    """
    mode = os.getenv("ADS_MODE", "mock").lower()

    if mode == "real":
        try:
            from .ads_client import ADSClient as _ADSClient
        except ImportError as exc:
            raise RuntimeError(
                "Modalità ADS_MODE=real richiede il pacchetto 'pyads'. "
                "Installalo con: pip install pyads"
            ) from exc
        from config import ads_cfg
        log.info("ADS factory: modalità REALE (%s)", ads_cfg.PLC_AMS_NET_ID)
        return _ADSClient(
            ams_net_id=ads_cfg.PLC_AMS_NET_ID,
            port=ads_cfg.PLC_PORT,
            poll_interval_ms=ads_cfg.POLL_INTERVAL_MS,
        )
    else:
        log.info("ADS factory: modalità MOCK")
        return MockADSClient(
            auto_trigger=True,
            tracking_interval_s=2.0,
            orientation_interval_s=2.5,
            inspection_interval_s=5.0,
        )


__all__ = [
    "BaseADSClient",
    "ADSClient",
    "MockADSClient",
    "create_ads_client",
]
