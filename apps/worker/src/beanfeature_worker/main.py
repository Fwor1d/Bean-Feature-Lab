import logging
import signal
from threading import Event

from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_research.contracts import RunStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    stop = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    container = create_container()
    logger.info("worker.start executor=not_implemented")
    reported: set[int] = set()
    try:
        while not stop.is_set():
            container.heartbeat.beat()
            queued = [
                run for run in container.service.list_runs() if run.status is RunStatus.QUEUED
            ]
            for run in queued:
                if run.id not in reported:
                    logger.warning(
                        "worker.run_deferred run_id=%s reason=research_engine_not_implemented",
                        run.display_id,
                    )
                    reported.add(run.id)
            stop.wait(5)
    finally:
        container.metadata.engine.dispose()
        logger.info("worker.stop")


if __name__ == "__main__":
    main()
