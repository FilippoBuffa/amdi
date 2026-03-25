"""
test_models.py
==============
Testa Piece, Batch e StatsManager.

Esegui con:
    python tests/test_models.py
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from piece import Piece, PieceStage, InspectionResult as PieceInspectionResult
from batch import Batch
from stats import StatsManager

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
# Piece
# ---------------------------------------------------------------------------
print("\n── Test Piece ──")

p = Piece()
check("Stage iniziale = CREATED", p.stage == PieceStage.CREATED)
check("ID non vuoto",             len(p.id) > 0)
check("Nessun dato tracking",     p.tracking_x is None)

p.set_tracking(123.5, 456.0, "/img/track.jpg")
check("Stage = TRACKED dopo set_tracking",  p.stage == PieceStage.TRACKED)
check("tracking_x corretto",               p.tracking_x == 123.5)
check("tracking_y corretto",               p.tracking_y == 456.0)
check("tracking_image_path corretto",      p.tracking_image_path == "/img/track.jpg")
check("tracking_ts valorizzato",           p.tracking_ts is not None)

p.set_orientation(45.0)
check("Stage = ORIENTED dopo set_orientation", p.stage == PieceStage.ORIENTED)
check("Angolo corretto",                        p.orientation_angle == 45.0)

p.set_inspection(PieceInspectionResult.OK, "batch-001", "/img/insp.jpg")
check("Stage = INSPECTED dopo set_inspection", p.stage == PieceStage.INSPECTED)
check("Risultato OK",                           p.inspection_result == PieceInspectionResult.OK)
check("batch_id corretto",                      p.batch_id == "batch-001")

d = p.to_dict()
check("to_dict ha tutte le chiavi",
      set(d.keys()) == {"id", "created_at", "stage", "tracking", "orientation", "inspection", "error"})
check("to_dict stage = 'inspected'",  d["stage"] == "inspected")
check("to_dict inspection result OK", d["inspection"]["result"] == "OK")
check("to_dict error = None",         d["error"] is None)

# Errore
p2 = Piece()
p2.mark_error("tracking", "camera timeout")
check("Stage = ERROR",         p2.stage == PieceStage.ERROR)
check("error_stage valorizzato", p2.error_stage == "tracking")
check("to_dict error non None", p2.to_dict()["error"] is not None)

# Timeout
p3 = Piece()
p3.mark_timeout()
check("Stage = TIMEOUT", p3.stage == PieceStage.TIMEOUT)


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
print("\n── Test Batch ──")

b = Batch()
check("Batch ID non vuoto",     len(b.id) > 0)
check("Batch non completo",     not b.completed)
check("size = 0 inizialmente",  b.size == 0)

b.piece_ids = ["p1", "p2", "p3", "p4"]
check("size = 4", b.size == 4)

from piece import InspectionResult as IR
b.complete(
    results=[IR.OK, IR.OK, IR.NG, IR.OK],
    image_path="/img/batch.jpg",
)
check("Batch completato",       b.completed)
check("ok_count = 3",           b.ok_count == 3)
check("ng_count = 1",           b.ng_count == 1)
check("all_ok = False",         not b.all_ok)
check("inspection_ts set",      b.inspection_ts is not None)

b2 = Batch()
b2.piece_ids = ["p1", "p2", "p3", "p4"]
b2.complete([IR.OK, IR.OK, IR.OK, IR.OK])
check("all_ok = True se tutti OK", b2.all_ok)

d = b.to_dict()
check("to_dict results corretto", d["results"] == ["OK", "OK", "NG", "OK"])
check("to_dict ng_count = 1",     d["ng_count"] == 1)


# ---------------------------------------------------------------------------
# StatsManager
# ---------------------------------------------------------------------------
print("\n── Test StatsManager ──")

sm = StatsManager(trend_window=10)
check("ng_rate iniziale = 0", sm.current.ng_rate == 0.0)
check("throughput iniziale = 0", sm.current.throughput_per_hour == 0.0)

sm.record_ok()
sm.record_ok()
sm.record_ok()
sm.record_ng()
check("total_pieces = 4",     sm.current.total_pieces == 4)
check("ok_pieces = 3",        sm.current.ok_pieces == 3)
check("ng_pieces = 1",        sm.current.ng_pieces == 1)
check("ng_rate = 25%",        abs(sm.current.ng_rate - 0.25) < 0.001)
check("ok_rate = 75%",        abs(sm.current.ok_rate - 0.75) < 0.001)

sm.record_batch(all_ok=True)
sm.record_batch(all_ok=False)
check("total_batches = 2",    sm.current.total_batches == 2)
check("full_ok_batches = 1",  sm.current.full_ok_batches == 1)

sm.record_timeout()
sm.record_error()
check("timeout_pieces = 1",   sm.current.timeout_pieces == 1)
check("error_pieces = 1",     sm.current.error_pieces == 1)

trend = sm.get_trend()
check("Trend ha 4 entry",     len(trend) == 4)
check("Trend entry ha 'ts'",  "ts" in trend[0])
check("Trend entry ha 'result'", "result" in trend[0])

# Ring buffer: non deve superare trend_window=10
for _ in range(20):
    sm.record_ok()
check("Ring buffer rispettato (max 10)", len(sm.get_trend()) == 10)

# Thread safety
sm2 = StatsManager()
barrier = threading.Barrier(5)

def worker():
    barrier.wait()
    for _ in range(100):
        sm2.record_ok()
        sm2.record_ng()

threads = [threading.Thread(target=worker) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

check("Thread safety: total_pieces = 1000",
      sm2.current.total_pieces == 1000, str(sm2.current.total_pieces))

# Reset
sm2.reset()
check("Reset: total_pieces = 0", sm2.current.total_pieces == 0)
check("Reset: trend vuoto",      len(sm2.get_trend()) == 0)

# to_dict
d = sm.to_dict()
check("to_dict ha 'current_shift'", "current_shift" in d)
check("to_dict ha 'trend'",         "trend" in d)
check("current_shift ha 'pieces'",  "pieces" in d["current_shift"])
check("current_shift ha 'rates'",   "rates" in d["current_shift"])


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
    print("✅ Tutti i test modelli OK")