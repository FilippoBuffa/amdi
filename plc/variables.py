"""
Mappa centralizzata di tutte le variabili ADS del progetto.
Prefisso TwinCAT: GVL_python.<nome>

Modifica SOLO questo file se i nomi cambiano nel progetto PLC.
"""

from __future__ import annotations
from dataclasses import dataclass

_GVL = "GVL_python"


@dataclass(frozen=True)
class _Vars:

    # ------------------------------------------------------------------
    # Python → PLC  |  Flags di stato telecamere (scritti all'avvio)
    # ------------------------------------------------------------------
    TRACKING_CAM_READY:    str = f"{_GVL}.bTrackingCamReady"     # BOOL
    ANGLE_CAM_READY:       str = f"{_GVL}.bAngleCamReady"        # BOOL
    INSPECTION_CAM_READY:  str = f"{_GVL}.bInspectionCamReady"   # BOOL
    CALIBRATION_READY:     str = f"{_GVL}.bCalibrationReady"     # BOOL

    # ------------------------------------------------------------------
    # Python → PLC  |  Risultati (scritti dopo ogni analisi)
    # ------------------------------------------------------------------
    COORDINATE_X:    str = f"{_GVL}.wCoordinateX"    # WORD  (centesimi di mm)
    COORDINATE_Y:    str = f"{_GVL}.wCoordinateY"    # WORD  (centesimi di mm)
    COORDINATE_A:    str = f"{_GVL}.iCoordinateA"    # BYTE  (gradi, 0-359)

    RES_ARRAY_1:     str = f"{_GVL}.aResArray[1]"    # BOOL  pezzo 1
    RES_ARRAY_2:     str = f"{_GVL}.aResArray[2]"    # BOOL  pezzo 2
    RES_ARRAY_3:     str = f"{_GVL}.aResArray[3]"    # BOOL  pezzo 3
    RES_ARRAY_4:     str = f"{_GVL}.aResArray[4]"    # BOOL  pezzo 4

    # ------------------------------------------------------------------
    # Python → PLC  |  Handshake "dati pronti"  (PLC li resetta a FALSE)
    # ------------------------------------------------------------------
    COORDINATE_READY: str = f"{_GVL}.bCoordinateReady"   # BOOL
    ANGLE_READY:      str = f"{_GVL}.bAngleReady"        # BOOL
    RESULTS_READY:    str = f"{_GVL}.bResultsReady"      # BOOL

    # ------------------------------------------------------------------
    # PLC → Python  |  Segnali letti dal backend
    # ------------------------------------------------------------------
    WATCHDOG:             str = f"{_GVL}.bWatchdog"             # BOOL  (TBD)
    QR_CODE_SCANNED:      str = f"{_GVL}.bQrCodeScanned"        # BOOL
    CALIBRATION_REQUEST:  str = f"{_GVL}.bCalibrationRequest"   # BOOL

    # ------------------------------------------------------------------
    # PLC → Python  |  Stato macchina (letto dall'HMI)
    # ------------------------------------------------------------------
    MACHINE_STATE:        str = f"{_GVL}.iMachineState"         # INT
    BTN_RESET_INHIBITED:  str = f"{_GVL}.bBtnResetinhibited"    # BOOL

    # ------------------------------------------------------------------
    # Python → PLC  |  Bottoni virtuali HMI (pulse TRUE quando premuto)
    # ------------------------------------------------------------------
    BTN_START:            str = f"{_GVL}.bBtnStart"             # BOOL
    BTN_STOP:             str = f"{_GVL}.bBtnStop"              # BOOL
    BTN_RESET:            str = f"{_GVL}.bBtnReset"             # BOOL

    # ------------------------------------------------------------------
    # Python → PLC  |  Comando richiesta modalità
    # ------------------------------------------------------------------
    STATUS_REQUEST:       str = f"{_GVL}.iStatusRequest"        # INT

    # ------------------------------------------------------------------
    # PLC → Python  |  Statistiche ciclo (aggiornate dal PLC ogni ciclo)
    # ------------------------------------------------------------------
    LEAK_TEST_1:    str = f"{_GVL}.aLeakTestResults[1]"     # BOOL
    LEAK_TEST_2:    str = f"{_GVL}.aLeakTestResults[2]"     # BOOL
    LEAK_TEST_3:    str = f"{_GVL}.aLeakTestResults[3]"     # BOOL
    LEAK_TEST_4:    str = f"{_GVL}.aLeakTestResults[4]"     # BOOL

    FLOW_TEST_1:    str = f"{_GVL}.aFlowTestResults[1]"     # BOOL
    FLOW_TEST_2:    str = f"{_GVL}.aFlowTestResults[2]"     # BOOL
    FLOW_TEST_3:    str = f"{_GVL}.aFlowTestResults[3]"     # BOOL
    FLOW_TEST_4:    str = f"{_GVL}.aFlowTestResults[4]"     # BOOL

    INSPECT_CAM_1:  str = f"{_GVL}.aInspectCamResults[1]"  # BOOL
    INSPECT_CAM_2:  str = f"{_GVL}.aInspectCamResults[2]"  # BOOL
    INSPECT_CAM_3:  str = f"{_GVL}.aInspectCamResults[3]"  # BOOL
    INSPECT_CAM_4:  str = f"{_GVL}.aInspectCamResults[4]"  # BOOL

    ALL_CLUSTER_1:  str = f"{_GVL}.aAllClusterResults[1]"  # BOOL
    ALL_CLUSTER_2:  str = f"{_GVL}.aAllClusterResults[2]"  # BOOL
    ALL_CLUSTER_3:  str = f"{_GVL}.aAllClusterResults[3]"  # BOOL
    ALL_CLUSTER_4:  str = f"{_GVL}.aAllClusterResults[4]"  # BOOL


VARS = _Vars()
