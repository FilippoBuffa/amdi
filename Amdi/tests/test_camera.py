"""
test_camera.py
==============
Testa il layer camera (MockCamera) senza hardware.

Esegui con:
    python tests/test_camera.py

Cosa testa:
  1. Apertura / chiusura camera
  2. Grab di frame e validazione shape / tipo
  3. Generazione immagini per tutti e 3 gli stage
  4. Cambio parametri (exposure, gain)
  5. Simulazione timeout
  6. Context manager
  7. Salvataggio immagini su disco per ispezione visiva
"""

import sys
import time
import logging
from pathlib import Path

# --- path setup ---
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import numpy as np
import cv2

from mock_camera import MockCamera
from base_camera import CameraState, CameraTimeoutError

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

OUTPUT_DIR = Path(__file__).parent / "output_images"
OUTPUT_DIR.mkdir(exist_ok=True)

PASS = "✅"
FAIL = "❌"
results = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    msg = f"{status} {name}"
    if detail:
        msg += f"  [{detail}]"
    print(msg)
    results.append((name, condition))


# ---------------------------------------------------------------------------
# 1. Apertura e chiusura
# ---------------------------------------------------------------------------
print("\n── Test 1: Apertura / Chiusura ──")

cam = MockCamera("tracking")
check("Stato iniziale = DISCONNECTED", cam.get_info().state == CameraState.DISCONNECTED)

cam.open()
check("Stato dopo open = CONNECTED", cam.get_info().state == CameraState.CONNECTED)

cam.close()
check("Stato dopo close = DISCONNECTED", cam.get_info().state == CameraState.DISCONNECTED)


# ---------------------------------------------------------------------------
# 2. Grab e validazione frame
# ---------------------------------------------------------------------------
print("\n── Test 2: Grab frame ──")

with MockCamera("tracking", width=1024, height=1024) as cam:
    frame = cam.grab()
    check("Frame non None",         frame is not None)
    check("Image è ndarray",        isinstance(frame.image, np.ndarray))
    check("Frame width = 1024",     frame.width == 1024)
    check("Frame height = 1024",    frame.height == 1024)
    check("Frame id > 0",           frame.frame_id > 0)
    check("Timestamp > 0",          frame.timestamp > 0)
    check("camera_id corretto",     frame.camera_id == "tracking")
    check("Immagine grayscale",     frame.is_gray)
    check("Dtype uint8",            frame.image.dtype == np.uint8)


# ---------------------------------------------------------------------------
# 3. Immagini sintetiche per tutti gli stage
# ---------------------------------------------------------------------------
print("\n── Test 3: Immagini sintetiche per stage ──")

stages = ["tracking", "orientation", "inspection"]
for stage in stages:
    with MockCamera(stage, width=512, height=512) as cam:
        frame = cam.grab()
        check(f"Grab {stage}",          frame is not None)
        check(f"{stage} non nera",      frame.image.max() > 10,
              f"max={frame.image.max()}")
        check(f"{stage} non bianca",    frame.image.min() < 250,
              f"min={frame.image.min()}")

        # Salva su disco per ispezione visiva
        out_path = OUTPUT_DIR / f"mock_{stage}.png"
        cv2.imwrite(str(out_path), frame.image)
        check(f"Immagine {stage} salvata", out_path.exists(), str(out_path))


# ---------------------------------------------------------------------------
# 4. Parametri exposure e gain
# ---------------------------------------------------------------------------
print("\n── Test 4: Parametri ──")

with MockCamera("tracking") as cam:
    cam.set_exposure(10000.0)
    check("set_exposure non lancia eccezioni", True)

    cam.set_gain(3.0)
    check("set_gain non lancia eccezioni", True)

    info = cam.get_info()
    check("get_info ritorna CameraInfo", info is not None)
    check("model contiene 'Mock'",       "Mock" in info.model)


# ---------------------------------------------------------------------------
# 5. Simulazione timeout
# ---------------------------------------------------------------------------
print("\n── Test 5: Timeout simulato ──")

cam_timeout = MockCamera("tracking", timeout_probability=1.0)  # sempre timeout
cam_timeout.open()
timeout_raised = False
try:
    cam_timeout.grab()
except CameraTimeoutError:
    timeout_raised = True
finally:
    cam_timeout.close()

check("CameraTimeoutError sollevata correttamente", timeout_raised)


# ---------------------------------------------------------------------------
# 6. Grab multipli e frame_id incrementale
# ---------------------------------------------------------------------------
print("\n── Test 6: Frame ID sequenziale ──")

with MockCamera("inspection", width=256, height=256) as cam:
    frames = [cam.grab() for _ in range(5)]
    ids = [f.frame_id for f in frames]
    check("Frame ID incrementale",      ids == list(range(1, 6)), str(ids))
    check("Timestamp crescente",        all(
        frames[i].timestamp <= frames[i+1].timestamp
        for i in range(len(frames)-1)
    ))


# ---------------------------------------------------------------------------
# 7. Performance: grab time
# ---------------------------------------------------------------------------
print("\n── Test 7: Performance grab ──")

with MockCamera("tracking", width=1024, height=1024) as cam:
    t0 = time.time()
    for _ in range(20):
        cam.grab()
    elapsed = time.time() - t0
    avg_ms = (elapsed / 20) * 1000
    check(f"20 grab in < 2s (avg {avg_ms:.1f}ms)", elapsed < 2.0, f"{elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 8. Context manager con eccezione (non deve lasciare camera aperta)
# ---------------------------------------------------------------------------
print("\n── Test 8: Context manager + eccezione ──")

cam2 = MockCamera("tracking")
try:
    with cam2:
        raise RuntimeError("errore intenzionale")
except RuntimeError:
    pass
check("Camera chiusa anche dopo eccezione",
      cam2.get_info().state == CameraState.DISCONNECTED)


# ---------------------------------------------------------------------------
# Riepilogo
# ---------------------------------------------------------------------------
print("\n" + "═" * 50)
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"Risultato: {passed}/{total} test passati")

if passed < total:
    print("\nTest FALLITI:")
    for name, ok in results:
        if not ok:
            print(f"  {FAIL} {name}")
    sys.exit(1)
else:
    print("✅ Tutti i test camera OK")
    print(f"\nImmagini sintetiche salvate in: {OUTPUT_DIR}/")