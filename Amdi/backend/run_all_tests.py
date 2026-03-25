"""
run_all_tests.py
================
Esegue tutti i test in sequenza e riporta un riepilogo finale.

Esegui con:
    python tests/run_all_tests.py
"""

import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).parent

tests = [
    ("Models",      TESTS_DIR / "test_models.py"),
    ("Camera",      TESTS_DIR / "test_camera.py"),
    ("PLC / ADS",   TESTS_DIR / "test_plc.py"),
    ("Integration", TESTS_DIR / "test_integration.py"),
]

results = []
total_start = time.time()

print("=" * 60)
print("  QC Machine — Test Suite")
print("=" * 60)

for name, path in tests:
    if not path.exists():
        print(f"\n⚠  {name}: file non trovato ({path}), skip.")
        continue

    print(f"\n▶  Esecuzione: {name} ({path.name})")
    print("-" * 60)

    start = time.time()
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=False,
    )
    elapsed = time.time() - start

    ok = proc.returncode == 0
    results.append((name, ok, elapsed))

print("\n" + "=" * 60)
print("  RIEPILOGO FINALE")
print("=" * 60)

for name, ok, elapsed in results:
    icon = "✅" if ok else "❌"
    print(f"  {icon}  {name:<20} {elapsed:.2f}s")

total_elapsed = time.time() - total_start
passed = sum(1 for _, ok, _ in results if ok)
total  = len(results)

print("-" * 60)
print(f"  {passed}/{total} suite passate  |  tempo totale: {total_elapsed:.2f}s")
print("=" * 60)

sys.exit(0 if passed == total else 1)
