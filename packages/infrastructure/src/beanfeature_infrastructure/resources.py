"""Process-tree resource measurement adapter for sequential local worker jobs."""

import platform
import time
from threading import Event, Thread

import psutil


def _process_tree_rss(process: psutil.Process) -> tuple[int, int]:
    total = 0
    alive = 0
    try:
        children = process.children(recursive=True)
    except (psutil.Error, PermissionError):
        children = []
    for item in (process, *children):
        try:
            total += item.memory_info().rss
            alive += 1
        except (psutil.Error, PermissionError):
            continue
    return total, max(0, alive - 1)


class ProcessTreeMeasurement:
    def __init__(self, sampling_interval_seconds: float) -> None:
        self.sampling_interval_seconds = sampling_interval_seconds
        self.process = psutil.Process()
        self.baseline_rss, _ = _process_tree_rss(self.process)
        self.samples: list[int] = []
        self.maximum_children = 0
        self.started = time.perf_counter()
        self.stop = Event()
        self.thread = Thread(target=self._sample, name="resource-rss-sampler", daemon=True)
        self.finished: dict[str, object] | None = None
        self.thread.start()

    def _sample(self) -> None:
        while not self.stop.is_set():
            rss, children = _process_tree_rss(self.process)
            self.samples.append(rss)
            self.maximum_children = max(self.maximum_children, children)
            self.stop.wait(self.sampling_interval_seconds)

    def finish(self) -> dict[str, object]:
        if self.finished is not None:
            return self.finished
        self.stop.set()
        self.thread.join(timeout=max(1.0, self.sampling_interval_seconds * 4))
        final_rss, children = _process_tree_rss(self.process)
        self.samples.append(final_rss)
        self.maximum_children = max(self.maximum_children, children)
        peak = max(self.samples)
        if peak <= 0:
            self.finished = {
                "status": "NOT_CALCULATED",
                "reason": "Process RSS was unavailable to the sampler",
                "sampling_interval_seconds": self.sampling_interval_seconds,
            }
            return self.finished
        self.finished = {
            "status": "CALCULATED",
            "measurement_kind": "isolated-run-process-tree-rss-v1",
            "scope": "fresh run process: dataset-load, nested-search, refit, and evaluation",
            "baseline_process_tree_rss_bytes": self.baseline_rss,
            "peak_process_tree_rss_bytes": peak,
            "incremental_peak_rss_bytes": max(0, peak - self.baseline_rss),
            "maximum_child_processes": self.maximum_children,
            "sampling_interval_seconds": self.sampling_interval_seconds,
            "rss_samples": len(self.samples),
            "measurement_wall_seconds": time.perf_counter() - self.started,
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
                "Sampled RSS includes the fresh run process and observed children. "
                "Incremental RSS is relative to the fresh child-process baseline and remains an "
                "engineering measurement, not a scientific outcome."
            ),
        }
        return self.finished


class ProcessTreeResourceMonitor:
    def __init__(self, sampling_interval_seconds: float = 0.01) -> None:
        if not 0.005 <= sampling_interval_seconds <= 1:
            raise ValueError("Sampling interval must be between 0.005 and 1 second")
        self.sampling_interval_seconds = sampling_interval_seconds

    def start(self) -> ProcessTreeMeasurement:
        return ProcessTreeMeasurement(self.sampling_interval_seconds)
