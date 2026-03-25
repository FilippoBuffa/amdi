"""
test_plc.py
===========
Testa il layer PLC (MockADSClient) senza hardware TwinCAT.

Esegui con:
    python tests/test_plc.py

Cosa testa:
  1. Connessione / disconnessione
  2. Trigger automatici (verifica che arrivino entro timeout)
  3. Trigger manuali
  4. Scrittura risultati (tracking, orientation, inspection)
  5. Cambio stato macchina (start/stop)
  6. Simulazione errore e recovery
  7. Disabilitazione auto-trigger a runtime
  8. Callback status change
"""

import sys
import time
import threading
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from mock_ads_client import MockADSClient
from base_ads_client import (
    PLCState,
    TrackingResult,
    OrientationResult,
    InspectionResult,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")

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
# 1. Connessione / disconnessione
# ---------------------------------------------------------------------------
print("\n── Test 1: Connessione / Disconnessione ──")

client = MockADSClient(auto_trigger=False)
check("Stato iniziale = DISCONNECTED",
      client.get_status().state == PLCState.DISCONNECTED)

client.start()
check("Stato dopo start = CONNECTED",
      client.get_status().state == PLCState.CONNECTED)
check("Machine running dopo start",
      client.get_status().machine_running)

client.stop()
check("Stato dopo stop = DISCONNECTED",
      client.get_status().state == PLCState.DISCONNECTED)


# ---------------------------------------------------------------------------
# 2. Trigger automatici
# ---------------------------------------------------------------------------
print("\n── Test 2: Trigger automatici ──")

counters = {"tracking": 0, "orientation": 0, "inspection": 0}

client = MockADSClient(
    auto_trigger=True,
    tracking_interval_s=0.2,
    orientation_interval_s=0.3,
    inspection_interval_s=0.4,
)
client.on_trigger_tracking(    lambda: counters.update({"tracking":    counters["tracking"]    + 1}))
client.on_trigger_orientation( lambda: counters.update({"orientation": counters["orientation"] + 1}))
client.on_trigger_inspection(  lambda: counters.update({"inspection":  counters["inspection"]  + 1}))

client.start()
time.sleep(1.2)
client.stop()

check("Tracking: >= 4 trigger automatici",    counters["tracking"]    >= 4, str(counters["tracking"]))
check("Orientation: >= 3 trigger automatici", counters["orientation"] >= 3, str(counters["orientation"]))
check("Inspection: >= 2 trigger automatici",  counters["inspection"]  >= 2, str(counters["inspection"]))


# ---------------------------------------------------------------------------
# 3. Trigger manuali
# ---------------------------------------------------------------------------
print("\n── Test 3: Trigger manuali ──")

manual = {"tracking": 0, "orientation": 0, "inspection": 0}

client = MockADSClient(auto_trigger=False)
client.on_trigger_tracking(    lambda: manual.update({"tracking":    manual["tracking"]    + 1}))
client.on_trigger_orientation( lambda: manual.update({"orientation": manual["orientation"] + 1}))
client.on_trigger_inspection(  lambda: manual.update({"inspection":  manual["inspection"]  + 1}))
client.start()

client.trigger_tracking()
client.trigger_orientation()
client.trigger_inspection()
client.trigger_tracking()   # secondo tracking

time.sleep(0.05)  # micro-sleep per dare tempo ai thread di processare
client.stop()

check("Trigger manuale tracking x2",    manual["tracking"]    == 2, str(manual["tracking"]))
check("Trigger manuale orientation x1", manual["orientation"] == 1, str(manual["orientation"]))
check("Trigger manuale inspection x1",  manual["inspection"]  == 1, str(manual["inspection"]))


# ---------------------------------------------------------------------------
# 4. Scrittura risultati
# ---------------------------------------------------------------------------
print("\n── Test 4: Scrittura risultati ──")

client = MockADSClient(auto_trigger=False)
client.start()

client.write_tracking_result(TrackingResult(x=150.5, y=320.0, ok=True))
client.write_tracking_result(TrackingResult(x=0.0,   y=0.0,   ok=False))
client.write_orientation_result(OrientationResult(angle=45.0, ok=True))
client.write_orientation_result(OrientationResult(angle=180.0, ok=True))
client.write_inspection_result(InspectionResult(results=[True, True, False, True]))
client.write_inspection_result(InspectionResult(results=[True, True, True, True]))

written = client.get_written_results()
client.stop()

check("2 risultati tracking scritti",     len(written["tracking"])    == 2)
check("Tracking[0] x=150.5",             written["tracking"][0]["x"] == 150.5)
check("Tracking[1] ok=False",            written["tracking"][1]["ok"] == False)
check("2 risultati orientation scritti",  len(written["orientation"])  == 2)
check("Orientation[0] angle=45.0",        written["orientation"][0]["angle"] == 45.0)
check("2 risultati inspection scritti",   len(written["inspection"])   == 2)
check("Inspection[0] risultati corretti", written["inspection"][0]["results"] == [True, True, False, True])


# ---------------------------------------------------------------------------
# 5. Start / Stop macchina
# ---------------------------------------------------------------------------
print("\n── Test 5: Stato macchina ──")

trigger_count = {"n": 0}
client = MockADSClient(auto_trigger=True, tracking_interval_s=0.1)
client.on_trigger_tracking(lambda: trigger_count.update({"n": trigger_count["n"] + 1}))
client.start()

time.sleep(0.3)
n_running = trigger_count["n"]

# Stop macchina: i trigger automatici devono fermarsi
client.set_machine_running(False)
time.sleep(0.3)
n_stopped = trigger_count["n"]

check("Machine running False: trigger si fermano",
      n_stopped == n_running, f"running={n_running} stopped={n_stopped}")

# Riparte
client.set_machine_running(True)
time.sleep(0.3)
n_restarted = trigger_count["n"]

check("Machine running True: trigger ripartono",
      n_restarted > n_stopped, f"after_restart={n_restarted}")

client.stop()


# ---------------------------------------------------------------------------
# 6. Simulazione errore e recovery
# ---------------------------------------------------------------------------
print("\n── Test 6: Errore e recovery ──")

status_log = []
client = MockADSClient(auto_trigger=False)
client.on_status_change(lambda s: status_log.append(s.state.value))
client.start()

client.simulate_error("Test error XY")
time.sleep(0.05)
check("Stato = ERROR dopo simulate_error",
      client.get_status().state == PLCState.ERROR)
check("error_message valorizzato",
      "XY" in (client.get_status().error_message or ""))

client.clear_error()
time.sleep(0.05)
check("Stato = CONNECTED dopo clear_error",
      client.get_status().state == PLCState.CONNECTED)

client.stop()

check("Status log contiene 'error'",   PLCState.ERROR.value   in status_log)
check("Status log contiene 'connected'", PLCState.CONNECTED.value in status_log)


# ---------------------------------------------------------------------------
# 7. Disabilita auto-trigger a runtime
# ---------------------------------------------------------------------------
print("\n── Test 7: Disabilita auto-trigger a runtime ──")

cnt = {"n": 0}
client = MockADSClient(auto_trigger=True, tracking_interval_s=0.1)
client.on_trigger_tracking(lambda: cnt.update({"n": cnt["n"] + 1}))
client.start()
time.sleep(0.35)
before = cnt["n"]

client.set_auto_trigger(False)
time.sleep(0.35)
after = cnt["n"]

client.stop()
check("Auto-trigger disabilitato: nessun nuovo trigger",
      after == before, f"before={before} after={after}")


# ---------------------------------------------------------------------------
# 8. Thread safety: trigger concorrenti
# ---------------------------------------------------------------------------
print("\n── Test 8: Thread safety ──")

shared_count = {"n": 0}
lock = threading.Lock()

def safe_inc():
    with lock:
        shared_count["n"] += 1

client = MockADSClient(
    auto_trigger=True,
    tracking_interval_s=0.05,
    orientation_interval_s=0.05,
    inspection_interval_s=0.05,
)
client.on_trigger_tracking(safe_inc)
client.on_trigger_orientation(safe_inc)
client.on_trigger_inspection(safe_inc)
client.start()
time.sleep(1.0)
client.stop()

check("Thread safety: contatore > 10 senza race conditions",
      shared_count["n"] > 10, str(shared_count["n"]))


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
    print("✅ Tutti i test PLC/ADS OK")