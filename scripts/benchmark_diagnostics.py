"""Compare identical stubbed workloads with and without diagnostic collection.

No provider calls or app databases are used. Run from the repository root.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import diagnostics as d  # noqa: E402
from services.api.middleware import RequestLoggingMiddleware  # noqa: E402
from services.api.logging_config import JsonFormatter  # noqa: E402


class DiscardOutput:
    """Measure console formatting without terminal rendering or file I/O."""

    def write(self, value):
        return len(value)

    def flush(self):
        pass


def percentile(values):
    return sorted(values)[max(0, int(len(values) * 0.95) - 1)]


def peak_rss_bytes():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class MemoryCounters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        reader = ctypes.windll.psapi.GetProcessMemoryInfo
        reader.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
        if not reader(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        return counters.PeakWorkingSetSize
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)


def benchmark(samples=200):
    os.environ["COLMILLO_DIAGNOSTICS_CONSOLE"] = "0"
    baseline_rss = peak_rss_bytes()
    with tempfile.TemporaryDirectory(prefix="colmillo-diagnostics-bench-") as folder:
        store = d.DiagnosticsStore(Path(folder) / "diagnostics.db")
        previous = d._store
        d._store = store
        assert store.ready.wait(5)
        measurements = {"disabled": [], "enabled": []}

        def workload(enabled):
            start = time.perf_counter()
            if enabled:
                with d.operation("benchmark", sport="nfl") as op:
                    for name in ("collect", "offers", "score", "save"):
                        with d.stage(name):
                            time.sleep(0.02)
                            d.emit("provider.completed", provider="stub", offer_count=10, cached=True)
                    op.finish("success", pick_count=3)
            else:
                for _ in range(4):
                    time.sleep(0.02)
            return (time.perf_counter() - start) * 1000

        # Alternate batches to limit ordering/temperature bias. Both use four workers.
        with ThreadPoolExecutor(max_workers=4) as pool:
            for _ in range(max(1, samples // 20)):
                for enabled in (False, True):
                    values = list(pool.map(workload, [enabled] * 20))
                    measurements["enabled" if enabled else "disabled"].extend(values)
        def make_app(enabled):
            app = FastAPI()
            if enabled:
                logger = logging.getLogger("diagnostics-benchmark")
                handler = logging.StreamHandler(DiscardOutput())
                handler.setFormatter(JsonFormatter())
                logger.handlers = [handler]
                logger.setLevel(logging.INFO)
                logger.propagate = False
                app.add_middleware(RequestLoggingMiddleware, logger=logger)

            @app.get("/stub")
            def stub():
                workload(enabled)
                return {"status": "success"}
            return app

        api_times = {False: [], True: []}
        with TestClient(make_app(False)) as disabled_client, TestClient(make_app(True)) as enabled_client:
            for _ in range(40):
                for enabled in (False, True):
                    start = time.perf_counter()
                    client = enabled_client if enabled else disabled_client
                    assert client.get("/stub").status_code == 200
                    api_times[enabled].append((time.perf_counter() - start) * 1000)
        api_added = percentile(api_times[True]) - percentile(api_times[False])
        # Trace allocations separately: allocation tracing changes Python execution
        # costs and would measure profiler overhead as application latency.
        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(workload, [True] * 40))
        peak_memory = tracemalloc.get_traced_memory()[1] - baseline_memory
        rss_added = peak_rss_bytes() - baseline_rss
        p95_disabled = percentile(measurements["disabled"])
        p95_enabled = percentile(measurements["enabled"])
        overhead = (p95_enabled / p95_disabled - 1) * 100
        health = store.health()
        store.close()
        d._store = previous
    tracemalloc.stop()
    return {"samples_per_mode": len(measurements["enabled"]), "concurrency": 4,
            "stub_delay_ms": 80, "disabled_p95_ms": round(p95_disabled, 3),
            "enabled_p95_ms": round(p95_enabled, 3), "p95_overhead_percent": round(overhead, 2),
            "enabled_median_ms": round(statistics.median(measurements["enabled"]), 3),
            "python_peak_added_mib": round(peak_memory / 1024**2, 3), "store_health": health,
            "process_peak_added_mib": round(rss_added / 1024**2, 3),
            "api_added_p95_ms": round(api_added, 3),
            "pass": overhead < 5 and peak_memory < 32 * 1024**2 and rss_added < 32 * 1024**2 and api_added < 10,
            "limitations": "Stubbed providers and ASGI requests on this host; no production traffic or real provider calls. RSS includes test harness growth. Allocation tracing uses a separate 40-operation pass, outside latency measurements."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=200)
    result = benchmark(parser.parse_args().samples)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
