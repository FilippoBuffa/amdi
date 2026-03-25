"""
test_basler_real.py
===================
Test con la telecamera Basler fisica connessa via GigE.
Salva i frame acquisiti in tests/output_images/ per ispezione visiva.

Esegui con:
    python3.11 tests/test_basler_real.py
    python3.11 tests/test_basler_real.py --ip 192.168.1.5   # IP diverso

Prerequisiti:
    - pip install pypylon opencv-python
    - Telecamera Basler raggiungibile all'IP specificato
"""

import sys
import argparse
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import cv2
import numpy as np

from basler_camera import BaslerCamera
from single_camera_simulator import SingleCameraSimulator
from base_camera import CameraTimeoutError, CameraConnectionError

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


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--ip", default="192.168.1.2", help="IP della telecamera Basler")
    p.add_argument("--exposure", type=float, default=10000.0, help="Exposure in µs")
    p.add_argument("--gain", type=float, default=0.0, help="Gain in dB")
    return p.parse_args()


def run_tests(ip: str, exposure_us: float, gain_db: float) -> None:

    # ---------------------------------------------------------------------------
    # 1. Connessione base
    # ---------------------------------------------------------------------------
    print(f"\n── Test 1: Connessione a {ip} ──")

    try:
        cam = BaslerCamera(camera_id="test", ip=ip, exposure_us=exposure_us, gain_db=gain_db)
        cam.open()
        check("Connessione riuscita", True)
    except CameraConnectionError as exc:
        check("Connessione riuscita", False, str(exc))
        print("\n❌ Camera non raggiungibile, test interrotti.")
        sys.exit(1)

    info = cam.get_info()
    print(f"   Modello:  {info.model}")
    print(f"   Serial:   {info.serial}")
    print(f"   Res:      {info.width}x{info.height}")
    check("get_info ha modello", len(info.model) > 0)
    check("get_info ha dimensioni", info.width > 0 and info.height > 0)

    # ---------------------------------------------------------------------------
    # 2. Grab singolo
    # ---------------------------------------------------------------------------
    print("\n── Test 2: Grab singolo ──")

    frame = cam.grab()
    check("Frame acquisito",          frame is not None)
    check("Image è ndarray",          isinstance(frame.image, np.ndarray))
    check("Dtype uint8",              frame.image.dtype == np.uint8)
    check("Image non nera",           frame.image.max() > 10,   f"max={frame.image.max()}")
    check("Image non saturata",       frame.image.mean() < 250, f"mean={frame.image.mean():.1f}")
    check("Dimensioni coerenti",      frame.width == info.width and frame.height == info.height)
    check("Timestamp valorizzato",    frame.timestamp > 0)

    out = OUTPUT_DIR / "basler_grab_single.png"
    cv2.imwrite(str(out), frame.image)
    check("Immagine salvata", out.exists(), str(out))

    # ---------------------------------------------------------------------------
    # 3. Grab multipli e frame ID
    # ---------------------------------------------------------------------------
    print("\n── Test 3: Grab multipli ──")

    frames = [cam.grab() for _ in range(5)]
    ids = [f.frame_id for f in frames]
    check("Frame ID incrementale", ids == list(range(2, 7)), str(ids))
    check("Timestamp crescente",   all(
        frames[i].timestamp <= frames[i+1].timestamp for i in range(4)
    ))

    # ---------------------------------------------------------------------------
    # 4. Cambio exposure
    # ---------------------------------------------------------------------------
    print("\n── Test 4: Cambio exposure ──")

    means = {}
    for exp in [2000, 10000, 30000]:
        cam.set_exposure(exp)
        time.sleep(0.1)   # lascia stabilizzare
        f = cam.grab()
        means[exp] = f.image.mean()
        print(f"   Exposure {exp:6d} µs → brightness media: {means[exp]:.1f}")

    check("Exposure bassa < exposure alta",
          means[2000] < means[30000],
          f"{means[2000]:.1f} < {means[30000]:.1f}")

    # Ripristina
    cam.set_exposure(exposure_us)

    # ---------------------------------------------------------------------------
    # 5. Cambio gain
    # ---------------------------------------------------------------------------
    print("\n── Test 5: Cambio gain ──")

    gain_means = {}
    for gain in [0, 6, 12]:
        cam.set_gain(gain)
        time.sleep(0.1)
        f = cam.grab()
        gain_means[gain] = f.image.mean()
        print(f"   Gain {gain:2d} dB → brightness media: {gain_means[gain]:.1f}")

    check("Gain alto > gain basso",
          gain_means[12] >= gain_means[0],
          f"{gain_means[12]:.1f} >= {gain_means[0]:.1f}")

    # Ripristina
    cam.set_gain(gain_db)

    # ---------------------------------------------------------------------------
    # 6. Performance
    # ---------------------------------------------------------------------------
    print("\n── Test 6: Performance ──")

    t0 = time.time()
    for _ in range(10):
        cam.grab()
    elapsed = time.time() - t0
    avg_ms = (elapsed / 10) * 1000
    print(f"   10 grab in {elapsed:.2f}s — media {avg_ms:.1f} ms/frame")
    check("10 grab in < 5s", elapsed < 5.0, f"{elapsed:.2f}s")

    cam.close()
    check("Close senza errori", True)

    # ---------------------------------------------------------------------------
    # 7. SingleCameraSimulator — usa la stessa camera per tutti e 3 gli stage
    # ---------------------------------------------------------------------------
    print("\n── Test 7: SingleCameraSimulator (3 stage, 1 camera) ──")

    with SingleCameraSimulator(ip=ip, exposure_us=exposure_us, gain_db=gain_db) as sim:
        for stage, grab_fn in [
            ("tracking",    sim.grab_tracking),
            ("orientation", sim.grab_orientation),
            ("inspection",  sim.grab_inspection),
        ]:
            f = grab_fn()
            check(f"Grab {stage}",           f is not None)
            check(f"{stage} camera_id ok",   f.camera_id == stage, f.camera_id)

            # Salva per ispezione visiva
            out = OUTPUT_DIR / f"basler_sim_{stage}.png"
            cv2.imwrite(str(out), f.image)
            check(f"{stage} immagine salvata", out.exists())

        # Verifica lock: grab concorrenti non devono crashare
        import threading
        errors = []

        def grab_thread(fn, name):
            try:
                for _ in range(3):
                    fn()
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        threads = [
            threading.Thread(target=grab_thread, args=(sim.grab_tracking,    "tracking")),
            threading.Thread(target=grab_thread, args=(sim.grab_orientation, "orientation")),
            threading.Thread(target=grab_thread, args=(sim.grab_inspection,  "inspection")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        check("Grab concorrenti senza errori", len(errors) == 0, str(errors))

    # ---------------------------------------------------------------------------
    # 8. Integrazione con MockADSClient + camera reale
    # ---------------------------------------------------------------------------
    print("\n── Test 8: Integrazione PLC mock + Camera reale ──")

    from mock_ads_client import MockADSClient
    from base_ads_client import TrackingResult

    cycle_count = {"n": 0}

    def on_trigger():
        with SingleCameraSimulator(ip=ip) as s:
            f = s.grab_tracking()
            # placeholder: usa centro immagine come posizione
            x = float(f.width / 2)
            y = float(f.height / 2)
            plc.write_tracking_result(TrackingResult(x=x, y=y, ok=True))
            cycle_count["n"] += 1

    plc = MockADSClient(auto_trigger=False)
    plc.on_trigger_tracking(on_trigger)
    plc.start()
    plc.trigger_tracking()
    plc.trigger_tracking()
    time.sleep(0.5)
    plc.stop()

    check("2 cicli trigger→grab→write completati",
          cycle_count["n"] == 2, str(cycle_count["n"]))

    written = plc.get_written_results()
    check("2 risultati scritti sul PLC mock",
          len(written["tracking"]) == 2)


# ---------------------------------------------------------------------------
# Riepilogo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    print(f"\n{'='*55}")
    print(f"  Basler Real Camera Test — IP: {args.ip}")
    print(f"{'='*55}")

    run_tests(args.ip, args.exposure, args.gain)

    print("\n" + "═" * 55)
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
        print(f"✅ Tutti i test OK")
        print(f"\nImmagini salvate in: {OUTPUT_DIR}/")
        print("  basler_grab_single.png  — grab singolo")
        print("  basler_sim_tracking.png — stage tracking")
        print("  basler_sim_orientation.png — stage orientation")
        print("  basler_sim_inspection.png  — stage inspection")