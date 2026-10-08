import sqlite3
import time
from threading import Event, Thread

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from beanfeature_infrastructure.database import Base, make_session_factory
from beanfeature_infrastructure.metadata import SQLiteWorkerHeartbeat
from beanfeature_worker.main import _heartbeat_loop


def test_real_sqlite_busy_heartbeat_recovers_after_reader_release(tmp_path):
    database = tmp_path / "heartbeat.sqlite"
    engine = create_engine(f"sqlite:///{database}", connect_args={"timeout": 0.05})
    Base.metadata.create_all(engine)
    heartbeat = SQLiteWorkerHeartbeat(make_session_factory(engine))
    heartbeat.beat()
    reader = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    reader.execute("BEGIN")
    original = reader.execute("SELECT seen_at FROM worker_heartbeat").fetchone()[0]
    busy, stop = Event(), Event()

    def beat():
        try:
            heartbeat.beat()
        except OperationalError:
            busy.set()
            raise

    thread = Thread(target=_heartbeat_loop, args=(stop, beat, 0.02))
    thread.start()
    try:
        assert busy.wait(3)
        assert thread.is_alive()
        assert reader.execute("SELECT seen_at FROM worker_heartbeat").fetchone()[0] == original
        reader.rollback()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            updated = reader.execute("SELECT seen_at FROM worker_heartbeat").fetchone()[0]
            if updated != original:
                break
            time.sleep(0.01)
        assert updated != original
        assert thread.is_alive()
    finally:
        reader.rollback()
        reader.close()
        stop.set()
        thread.join(timeout=3)
        engine.dispose()
    assert not thread.is_alive()


def test_non_lock_database_failure_is_not_hidden(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'broken.sqlite'}")

    def beat():
        with engine.begin() as connection:
            connection.execute(text("SELECT * FROM missing_heartbeat_table"))

    try:
        with pytest.raises(OperationalError, match="missing_heartbeat_table"):
            _heartbeat_loop(Event(), beat, 0.01)
    finally:
        engine.dispose()
