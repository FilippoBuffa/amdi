"""
Mappa centralizzata di tutte le variabili ADS del progetto TwinCAT 3.
Modifica qui i nomi simbolici se cambia il progetto PLC,
senza toccare il resto del codice.

Convenzione TwinCAT 3: "<TaskName>.<NomeVariabile>"
"""

from dataclasses import dataclass
import pyads


@dataclass(frozen=True)
class ADSVariables:
    """Nomi simbolici delle variabili PLC."""

    # ------------------------------------------------------------------
    # Trigger: il PLC scrive TRUE → il backend acquisisce → resetta a FALSE
    # ------------------------------------------------------------------
    TRIGGER_TRACKING:    str = "MAIN.bTriggerTracking"
    TRIGGER_ORIENTATION: str = "MAIN.bTriggerOrientation"
    TRIGGER_INSPECTION:  str = "MAIN.bTriggerInspection"

    # ------------------------------------------------------------------
    # Risultati tracking (backend → PLC)
    # ------------------------------------------------------------------
    RESULT_TRACKING_X:  str = "MAIN.fTrackingX"     # LREAL
    RESULT_TRACKING_Y:  str = "MAIN.fTrackingY"     # LREAL
    RESULT_TRACKING_OK: str = "MAIN.bTrackingOK"    # BOOL

    # ------------------------------------------------------------------
    # Risultati orientamento (backend → PLC)
    # ------------------------------------------------------------------
    RESULT_ANGLE:          str = "MAIN.fOrientationAngle"  # LREAL  (gradi)
    RESULT_ORIENTATION_OK: str = "MAIN.bOrientationOK"     # BOOL

    # ------------------------------------------------------------------
    # Risultati ispezione (backend → PLC)
    # Array BOOL[0..3] — un elemento per pezzo nel batch
    # ------------------------------------------------------------------
    RESULT_INSPECTION_0:  str = "MAIN.bInspectionResult[0]"  # BOOL
    RESULT_INSPECTION_1:  str = "MAIN.bInspectionResult[1]"  # BOOL
    RESULT_INSPECTION_2:  str = "MAIN.bInspectionResult[2]"  # BOOL
    RESULT_INSPECTION_3:  str = "MAIN.bInspectionResult[3]"  # BOOL
    RESULT_INSPECTION_OK: str = "MAIN.bInspectionDone"       # BOOL (handshake)

    # ------------------------------------------------------------------
    # Stato macchina (PLC → backend, read-only)
    # ------------------------------------------------------------------
    MACHINE_RUNNING: str = "MAIN.bMachineRunning"  # BOOL
    MACHINE_ERROR:   str = "MAIN.bMachineError"    # BOOL


# Tipi pyads associati a ogni variabile (usati per read/write tipizzati)
ADS_TYPE_MAP: dict[str, type] = {
    ADSVariables.TRIGGER_TRACKING:    pyads.constants.PLCTYPE_BOOL,
    ADSVariables.TRIGGER_ORIENTATION: pyads.constants.PLCTYPE_BOOL,
    ADSVariables.TRIGGER_INSPECTION:  pyads.constants.PLCTYPE_BOOL,

    ADSVariables.RESULT_TRACKING_X:   pyads.constants.PLCTYPE_LREAL,
    ADSVariables.RESULT_TRACKING_Y:   pyads.constants.PLCTYPE_LREAL,
    ADSVariables.RESULT_TRACKING_OK:  pyads.constants.PLCTYPE_BOOL,

    ADSVariables.RESULT_ANGLE:          pyads.constants.PLCTYPE_LREAL,
    ADSVariables.RESULT_ORIENTATION_OK: pyads.constants.PLCTYPE_BOOL,

    ADSVariables.RESULT_INSPECTION_0:  pyads.constants.PLCTYPE_BOOL,
    ADSVariables.RESULT_INSPECTION_1:  pyads.constants.PLCTYPE_BOOL,
    ADSVariables.RESULT_INSPECTION_2:  pyads.constants.PLCTYPE_BOOL,
    ADSVariables.RESULT_INSPECTION_3:  pyads.constants.PLCTYPE_BOOL,
    ADSVariables.RESULT_INSPECTION_OK: pyads.constants.PLCTYPE_BOOL,

    ADSVariables.MACHINE_RUNNING: pyads.constants.PLCTYPE_BOOL,
    ADSVariables.MACHINE_ERROR:   pyads.constants.PLCTYPE_BOOL,
}

# Istanza singleton importabile ovunque
VARS = ADSVariables()
