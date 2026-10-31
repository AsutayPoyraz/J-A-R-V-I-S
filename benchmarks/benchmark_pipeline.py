"""Repeatable local-command, verifier, and cold-import measurements."""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import timeit
import tracemalloc
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def benchmark_callable(
    callable_obj,
    number: int = 100,
    repeats: int = 5,
) -> dict[str, float]:
    if number < 1 or repeats < 1:
        raise ValueError("number ve repeats pozitif olmalı.")

    samples = timeit.repeat(callable_obj, number=number, repeat=repeats)
    sample_ms = [sample * 1000 / number for sample in samples]
    tracemalloc.start()
    try:
        for _ in range(number):
            callable_obj()
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    ordered = sorted(sample_ms)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "runs_per_sample": float(number),
        "samples": float(repeats),
        "average_ms": statistics.mean(sample_ms),
        "median_ms": statistics.median(sample_ms),
        "p95_sample_ms": ordered[p95_index],
        "python_peak_allocated_kib": peak_bytes / 1024,
    }


def benchmark_cold_import(repeats: int = 3) -> dict[str, float]:
    if repeats < 1:
        raise ValueError("repeats pozitif olmalı.")
    code = (
        "import json, time; "
        "start=time.perf_counter(); "
        "import jarvis_v11; "
        "elapsed=(time.perf_counter()-start)*1000; "
        "rss=None; "
        "import psutil; "
        "rss=psutil.Process().memory_info().rss/1024/1024; "
        "print(json.dumps({'import_ms': elapsed, 'rss_mib': rss}))"
    )
    launches = []
    imports = []
    rss_values = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=90,
        )
        launches.append((time.perf_counter() - start) * 1000)
        output = json.loads(result.stdout.strip().splitlines()[-1])
        imports.append(float(output["import_ms"]))
        if output["rss_mib"] is not None:
            rss_values.append(float(output["rss_mib"]))

    report = {
        "samples": float(repeats),
        "mean_process_launch_ms": statistics.mean(launches),
        "mean_module_import_ms": statistics.mean(imports),
    }
    if rss_values:
        report["mean_import_process_rss_mib"] = statistics.mean(rss_values)
    return report


def run_benchmarks(number: int = 100, repeats: int = 5) -> dict[str, dict[str, float]]:
    from services.offline_commands import handle_offline_command
    from services.verification import CommandVerifier

    return {
        "offline_clock_command": benchmark_callable(
            lambda: handle_offline_command("saat kaç"),
            number=number,
            repeats=repeats,
        ),
        "offline_calculation_command": benchmark_callable(
            lambda: handle_offline_command("hesapla: 125 * (24 + 6)"),
            number=number,
            repeats=repeats,
        ),
        "safe_command_verification": benchmark_callable(
            lambda: CommandVerifier().inspect("hava durumu"),
            number=number,
            repeats=repeats,
        ),
        "risk_command_verification": benchmark_callable(
            lambda: CommandVerifier().inspect("dosyaları sil"),
            number=number,
            repeats=repeats,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--skip-cold-import",
        action="store_true",
        help="Soğuk JARVIS import/RAM ölçümünü atla.",
    )
    args = parser.parse_args()
    print(json.dumps(run_benchmarks(args.number, args.repeats), indent=2))
    if not args.skip_cold_import:
        print(
            "cold_import:",
            json.dumps(benchmark_cold_import(), indent=2),
        )
    print(
        "Not: import belleği ve süre ölçümleri bu makineye özeldir; "
        "gerçek UI açılışını veya 1 kbit/s ağ hızını ölçmez."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
