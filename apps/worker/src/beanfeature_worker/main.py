import logging
import signal
import sqlite3
from collections.abc import Callable
from multiprocessing import get_context
from queue import Empty
from threading import Event, Thread

from sqlalchemy.exc import OperationalError

from beanfeature_infrastructure.bootstrap import create_container

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _heartbeat_loop(stop: Event, beat: Callable[[], None], interval: float = 5) -> None:
    while not stop.is_set():
        try:
            beat()
        except OperationalError as exc:
            code = getattr(exc.orig, "sqlite_errorcode", None)
            if code is None or code & 0xFF not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise
            # The session context rolls back. Retry a transient lock without claiming freshness.
            logger.warning("worker.heartbeat_busy retry_after_seconds=%s", interval)
        stop.wait(interval)


def _process_one(stop, output) -> None:  # type: ignore[no-untyped-def]
    """Execute at most one queued run in a fresh resource-measured process."""
    container = create_container(measure_process_resources=True)
    try:
        run = container.service.process_next_run(should_stop=stop.is_set)
        if run is None:
            output.put(None)
        else:
            output.put({"display_id": run.display_id, "status": run.status.value})
    except Exception as exc:
        output.put({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        container.metadata.engine.dispose()


def main() -> None:
    stop = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    container = create_container()
    recovered = container.service.recover_interrupted_runs()
    logger.info("worker.start executor=nested_cv recovered_failed=%s", recovered)

    heartbeat_thread = Thread(
        target=_heartbeat_loop,
        args=(stop, container.heartbeat.beat),
        name="beanfeature-heartbeat",
        daemon=True,
    )
    heartbeat_thread.start()
    context = get_context("spawn")
    try:
        while not stop.is_set():
            if not any(run.status.value == "QUEUED" for run in container.service.list_runs()):
                stop.wait(2)
                continue
            child_stop = context.Event()
            output = context.Queue()
            process = context.Process(
                target=_process_one,
                args=(child_stop, output),
                name="beanfeature-run",
            )
            process.start()
            while process.is_alive():
                if stop.is_set():
                    child_stop.set()
                process.join(timeout=0.5)
            try:
                result = output.get(timeout=2)
            except Empty:
                result = {"error": f"run child exited with code {process.exitcode}"}
            finally:
                output.close()
                output.join_thread()
            if result is None:
                stop.wait(1)
            elif "error" in result:
                logger.error("worker.child_failed detail=%s", result["error"])
            else:
                logger.info(
                    "worker.run_finished run_id=%s status=%s",
                    result["display_id"],
                    result["status"],
                )
    finally:
        stop.set()
        heartbeat_thread.join(timeout=6)
        container.metadata.engine.dispose()
        logger.info("worker.stop")


if __name__ == "__main__":
    main()
