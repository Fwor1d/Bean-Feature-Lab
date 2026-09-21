import logging
import signal
from threading import Event, Thread

from beanfeature_infrastructure.bootstrap import create_container

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    stop = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    container = create_container()
    recovered = container.service.recover_interrupted_runs()
    logger.info("worker.start executor=nested_cv recovered_failed=%s", recovered)

    def heartbeat() -> None:
        while not stop.is_set():
            container.heartbeat.beat()
            stop.wait(5)

    heartbeat_thread = Thread(target=heartbeat, name="beanfeature-heartbeat", daemon=True)
    heartbeat_thread.start()
    try:
        while not stop.is_set():
            run = container.service.process_next_run(should_stop=stop.is_set)
            if run is None:
                stop.wait(2)
            else:
                logger.info(
                    "worker.run_finished run_id=%s status=%s", run.display_id, run.status.value
                )
    finally:
        stop.set()
        heartbeat_thread.join(timeout=6)
        container.metadata.engine.dispose()
        logger.info("worker.stop")


if __name__ == "__main__":
    main()
