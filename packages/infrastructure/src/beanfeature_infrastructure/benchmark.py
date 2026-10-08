"""Isolated deployment benchmarks, separate from scientific CV evaluation."""

import platform
import time
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from statistics import median
from threading import Event, Thread

import numpy as np
import psutil

from .datasets import UCIDatasetStore
from .deployment import LocalDeploymentModelStore


def _process_tree_rss(process: psutil.Process) -> tuple[int, int]:
    processes = [process, *process.children(recursive=True)]
    total = 0
    alive = 0
    for item in processes:
        try:
            total += item.memory_info().rss
            alive += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total, max(0, alive - 1)


def _worker(
    queue,  # type: ignore[no-untyped-def]
    model_root: str,
    data_root: str,
    repeats: int,
    sampling_interval_seconds: float,
) -> None:
    process = psutil.Process()
    baseline_rss, _ = _process_tree_rss(process)
    samples: list[int] = []
    max_children = 0
    stop = Event()

    def sample() -> None:
        nonlocal max_children
        while not stop.is_set():
            rss, children = _process_tree_rss(process)
            samples.append(rss)
            max_children = max(max_children, children)
            stop.wait(sampling_interval_seconds)

    sampler = Thread(target=sample, daemon=True)
    sampler.start()
    try:
        pipeline, metadata = LocalDeploymentModelStore(Path(model_root)).load()
        dataset, manifest = UCIDatasetStore(Path(data_root)).load()
        if metadata["dataset_sha256"] != dataset.arff_sha256:
            raise ValueError("Deployment model and benchmark dataset hashes differ")
        timings: dict[str, dict[str, object]] = {}
        for label, count in (("single_row", 1), ("batch_1000", 1000)):
            frame = dataset.features.iloc[:count]
            for _ in range(5):
                pipeline.predict_proba(frame)
            values = []
            for _ in range(repeats):
                started = time.perf_counter_ns()
                pipeline.predict_proba(frame)
                values.append((time.perf_counter_ns() - started) / 1_000_000)
            timings[label] = {
                "rows": count,
                "repeats": repeats,
                "median_ms": median(values),
                "p95_ms": float(np.percentile(values, 95)),
                "samples_ms": values,
            }
        final_rss, final_children = _process_tree_rss(process)
        samples.append(final_rss)
        max_children = max(max_children, final_children)
        model_path = Path(model_root) / f"{metadata['model_id']}.joblib"
        queue.put(
            {
                "status": "CALCULATED",
                "benchmark_kind": "isolated-deployment-full-pipeline-v1",
                "model_id": metadata["model_id"],
                "source_run": metadata["source_run"],
                "dataset_sha256": manifest["arff_sha256"],
                "peak_process_tree_rss_bytes": max(samples),
                "baseline_process_tree_rss_bytes": baseline_rss,
                "incremental_peak_rss_bytes": max(0, max(samples) - baseline_rss),
                "maximum_child_processes": max_children,
                "sampling_interval_seconds": sampling_interval_seconds,
                "rss_samples": len(samples),
                "latency": timings,
                "serialized_pipeline_bytes": model_path.stat().st_size,
                "warmup_repetitions": 5,
                "hardware": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "logical_cpu_count": psutil.cpu_count(logical=True),
                    "physical_cpu_count": psutil.cpu_count(logical=False),
                    "total_memory_bytes": psutil.virtual_memory().total,
                },
                "note": (
                    "Engineering benchmark in a fresh process. RSS includes the process and all "
                    "observed children; it is not a scientific accuracy result."
                ),
            }
        )
    except Exception as exc:
        queue.put({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        stop.set()
        sampler.join(timeout=1)


def benchmark_deployment_model(
    *,
    model_root: Path = Path("artifacts/models"),
    data_root: Path = Path("data"),
    repeats: int = 30,
    sampling_interval_seconds: float = 0.01,
    timeout_seconds: float = 180,
) -> dict[str, object]:
    """Run the benchmark in a spawned process so RSS starts from a defined baseline."""
    if not 5 <= repeats <= 1_000:
        raise ValueError("Benchmark repeats must be between 5 and 1000")
    if not 0.005 <= sampling_interval_seconds <= 1:
        raise ValueError("Sampling interval must be between 0.005 and 1 second")
    context = get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_worker,
        args=(
            queue,
            str(model_root.resolve()),
            str(data_root.resolve()),
            repeats,
            sampling_interval_seconds,
        ),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        raise TimeoutError("Deployment benchmark exceeded its timeout")
    try:
        result = queue.get(timeout=2)
    except Empty as exc:
        raise RuntimeError(f"Deployment benchmark exited with code {process.exitcode}") from exc
    if not isinstance(result, dict) or result.get("status") != "CALCULATED":
        raise RuntimeError(str(result.get("error", "Deployment benchmark failed")))
    return result
