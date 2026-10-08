"""Exercise lifecycle with real subprocesses and HTTP, without any ML execution."""

import importlib.util
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/presentation.py"
spec = importlib.util.spec_from_file_location("presentation", SCRIPT)
presentation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = presentation
spec.loader.exec_module(presentation)


def eventually(condition, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.1)
    raise AssertionError("Lifecycle condition timed out")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def lifecycle(tmp_path):
    root = tmp_path
    (root / "storage/sqlite").mkdir(parents=True)
    with sqlite3.connect(root / "storage/sqlite/beanfeature.sqlite") as connection:
        connection.execute("CREATE TABLE worker_heartbeat(id INTEGER PRIMARY KEY,seen_at TEXT)")
    service = root / "service.py"
    service.write_text("""
import json,sqlite3,sys,time,subprocess
from datetime import UTC,datetime
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
role=sys.argv[1]
if role=='worker':
    while True:
        if not Path('freeze').exists():
            with sqlite3.connect('storage/sqlite/beanfeature.sqlite') as db:
                stamp=datetime.now(UTC).isoformat()
                db.execute('INSERT OR REPLACE INTO worker_heartbeat VALUES(1,?)',(stamp,))
        time.sleep(.1)
elif role=='sleep':
    time.sleep(1000)
elif role=='exit':
    sys.exit(17)
elif role=='orphan':
    child=subprocess.Popen([sys.executable,__file__,'sleep'])
    Path('orphan.pid').write_text(str(child.pid))
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            ready=not Path('not-ready').exists()
            self.send_response(200 if ready else 503); self.end_headers()
            body={'application':'beanfeature-'+role,
                'status':'ready' if ready else 'not_ready','read_only':True}
            self.wfile.write(json.dumps(body).encode())
        def log_message(self,*args):pass
    HTTPServer(('127.0.0.1',int(sys.argv[2])),Handler).serve_forever()
""")
    api, web = free_port(), free_port()
    config = presentation.Config(
        root=root,
        local_api=f"http://127.0.0.1:{api}",
        local_web=f"http://127.0.0.1:{web}",
        public_api=f"http://127.0.0.1:{api}",
        public_web=f"http://127.0.0.1:{web}",
        check_interval=0.2,
        public_interval=0.3,
        startup_timeout=3,
        shutdown_timeout=1,
    )
    runner = root / "runner.py"
    runner.write_text(f"""
import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('presentation',{str(SCRIPT)!r})
p=importlib.util.module_from_spec(spec);sys.modules[spec.name]=p;spec.loader.exec_module(p)
c=p.Config(root=Path({str(root)!r}),local_api={config.local_api!r},local_web={config.local_web!r},public_api={config.public_api!r},public_web={config.public_web!r},check_interval=.2,public_interval=.3,startup_timeout=3,shutdown_timeout=1)
p.named_tunnel_running=lambda:False
class Demo(p.Supervisor):
    def preflight(self):
        for port in ({api},{web}):p.port_conflict(port)
    def start_components(self):
        self.spawn('sleep',[sys.executable,'service.py','sleep'])
        self.spawn('api',[sys.executable,'service.py','api',{str(api)!r}])
        self.wait('API',lambda:p.probe(c.local_api+'/ready','beanfeature-api',read_only=True)=='ready')
        worker_role='exit' if Path('fail').exists() else 'worker'
        self.spawn('worker',[sys.executable,'service.py',worker_role])
        self.wait('worker',lambda:p.heartbeat(c,self.state['owned']['worker'])=='online')
        self.spawn('web',[sys.executable,'service.py','web',{str(web)!r}])
        self.wait('web',lambda:p.probe(c.local_web+'/api/ready','beanfeature-web')=='ready')
sys.exit(Demo(c).run())
""")
    children = []

    def start():
        process = subprocess.Popen(
            [sys.executable, str(runner)],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        children.append(process)
        return process

    yield config, start
    try:
        presentation.stop_session(config)
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=3)


def state(config):
    return presentation.read_state(config)


def serving(config):
    return state(config).get("phase") == "serving"


def assert_clean(config):
    for record in state(config).get("owned", {}).values():
        assert not presentation.group_members(record)


def test_real_round_trip_duplicate_start_and_repeated_stop(lifecycle, monkeypatch):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    first = state(config)["owned"]
    duplicate = start()
    assert duplicate.wait(timeout=8) == 0
    assert state(config)["owned"] == first
    monkeypatch.setattr(presentation, "named_tunnel_running", lambda: False)
    status = presentation.operational_status(config, state(config))
    assert status["api"] == status["web"] == "ready"
    assert status["worker"] == "online"
    assert status["sleep"] == "active"
    assert status["tunnel"] == "offline"
    assert status["public"] == {"api": "ready", "web": "ready"}
    presentation.stop_session(config)
    assert process.wait(timeout=8) == 0
    presentation.stop_session(config)
    assert_clean(config)
    assert presentation.operational_status(config, state(config))["worker"] == "stopped"


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signals_cleanup_all_owned_groups(lifecycle, signum):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    process.send_signal(signum)
    assert process.wait(timeout=8) == 0
    assert_clean(config)


def test_partial_startup_failure_and_unrelated_process_survives(lifecycle):
    config, start = lifecycle
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(100)"], start_new_session=True
    )
    try:
        (config.root / "fail").touch()
        process = start()
        assert process.wait(timeout=8) == 1
        assert "worker exited" in state(config)["failure"]
        assert "api" in state(config)["owned"]
        assert_clean(config)
        assert unrelated.poll() is None
        assert list(Path(state(config)["logs"]).glob("*.log"))
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_unrelated_port_conflict_is_not_killed(lifecycle):
    config, start = lifecycle
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", int(config.local_api.rsplit(":", 1)[1])))
        listener.listen()
        assert start().wait(timeout=8) == 1
        assert "occupied" in state(config)["failure"]
        assert state(config)["owned"] == {}
        assert listener.fileno() >= 0


def test_component_exit_is_detected_and_cleans_session(lifecycle):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    os.kill(state(config)["owned"]["web"]["pid"], signal.SIGTERM)
    assert process.wait(timeout=8) == 1
    assert "web exited" in state(config)["failure"]
    assert_clean(config)


def test_stale_heartbeat_is_detected_with_worker_still_alive(lifecycle):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    (config.root / "freeze").touch()
    time.sleep(0.3)
    with sqlite3.connect(config.db_path) as db:
        db.execute(
            "UPDATE worker_heartbeat SET seen_at=?",
            ((datetime.now(UTC) - timedelta(seconds=40)).isoformat(),),
        )
    assert process.wait(timeout=8) == 1
    assert "heartbeat is stale" in state(config)["failure"]
    assert_clean(config)


def test_readiness_failure_not_just_process_alive(lifecycle):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    (config.root / "not-ready").touch()
    assert process.wait(timeout=8) == 1
    assert "readiness failed three" in state(config)["failure"]
    assert_clean(config)


def test_stale_reused_pid_state_does_not_kill_unrelated_process(lifecycle):
    config, start = lifecycle
    presentation.lock_session(config).close()
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(100)"], start_new_session=True
    )
    try:
        record = presentation.identity(unrelated.pid)
        record["created"] -= 1
        presentation.save_state(
            config,
            {
                "version": 1,
                "root": str(config.root),
                "phase": "serving",
                "owner": record,
                "owned": {"api": record},
            },
        )
        process = start()
        eventually(lambda: serving(config) and state(config)["owner"]["pid"] == process.pid)
        assert unrelated.poll() is None
        presentation.stop_session(config)
        assert process.wait(timeout=8) == 0
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_orphaned_descendant_group_cleanup(lifecycle):
    config, _ = lifecycle
    process = subprocess.Popen(
        [sys.executable, "service.py", "orphan"], cwd=config.root, start_new_session=True
    )
    record = presentation.identity(process.pid)
    assert process.wait(timeout=3) == 0
    child = psutil.Process(int((config.root / "orphan.pid").read_text()))
    assert child.is_running()
    presentation.cleanup_groups({"orphan": record}, timeout=1)
    eventually(lambda: not child.is_running() or child.status() == psutil.STATUS_ZOMBIE)


def test_public_failure_is_separate_from_local_readiness(lifecycle, monkeypatch):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    snapshot = state(config)
    snapshot["public_api"] = snapshot["public_web"] = "http://127.0.0.1:1"
    monkeypatch.setattr(presentation, "named_tunnel_running", lambda: True)
    status = presentation.operational_status(config, snapshot)
    assert status["tunnel"] == "external_process"
    assert status["public"] == {"api": "unreachable", "web": "unreachable"}
    assert status["api"] == status["web"] == "ready"
    assert process.poll() is None


def test_public_probe_rejects_unexpected_identity_and_unsafe_url(lifecycle):
    config, start = lifecycle
    start()
    eventually(lambda: serving(config))
    assert presentation.probe(config.local_api + "/ready", "other") == "unexpected_response"
    for value in (
        "http://demo.example",
        "https://token@demo.example",
        "https://demo.example?token=secret",
    ):
        with pytest.raises(ValueError):
            presentation.public_url(value)


def test_logs_rotate_and_retention_is_bounded(lifecycle):
    config, _ = lifecycle
    supervisor = presentation.Supervisor(config)
    logs = config.root / "logs"
    logs.mkdir()
    supervisor.state = {"logs": str(logs)}
    logger = supervisor.log("example")
    for _ in range(400):
        logger.info("x" * 8192)
    for handler in supervisor.handlers:
        handler.close()
    assert len(list(logs.iterdir())) == 2
    assert sum(path.stat().st_size for path in logs.iterdir()) <= 2 * presentation.LOG_BYTES


def test_tunnel_inspection_failure_is_unknown_not_local_failure(lifecycle, monkeypatch):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    monkeypatch.setattr(presentation, "named_tunnel_running", lambda: None)
    status = presentation.operational_status(config, state(config))
    assert status["tunnel"] == "unknown"
    assert status["api"] == status["web"] == "ready"
    assert process.poll() is None


def test_tunnel_process_race_is_safe_and_arguments_not_reported(monkeypatch):
    responses = iter(
        [
            subprocess.CompletedProcess([], 0, "748 /opt/homebrew/bin/cloudflared\n", ""),
            subprocess.CompletedProcess([], 1, "", ""),
        ]
    )
    monkeypatch.setattr(presentation.subprocess, "run", lambda *args, **kwargs: next(responses))
    assert presentation.named_tunnel_running() is False


def test_malformed_identity_fails_without_signals(lifecycle):
    config, _ = lifecycle
    presentation.lock_session(config).close()
    presentation.save_state(
        config,
        {"version": 1, "root": str(config.root), "owner": {"pid": 1, "created": 0}, "owned": {}},
    )
    with pytest.raises(RuntimeError, match="Invalid process identity"):
        presentation.stop_session(config)
    (config.state_dir / "session.json").unlink()


def test_state_write_failure_still_cleans_started_process(lifecycle, monkeypatch):
    config, _ = lifecycle
    supervisor = presentation.Supervisor(config)
    monkeypatch.setattr(supervisor, "preflight", lambda: None)
    monkeypatch.setattr(
        supervisor,
        "start_components",
        lambda: supervisor.spawn("worker", [sys.executable, "service.py", "sleep"]),
    )
    original = supervisor.publish
    calls = 0

    def fail_after_initial_state():
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("simulated state disk failure")
        original()

    monkeypatch.setattr(supervisor, "publish", fail_after_initial_state)
    assert supervisor.run() == 1
    assert not presentation.group_members(supervisor.state["owned"]["worker"])


def test_quick_url_detection_and_owned_tunnel_cleanup(lifecycle):
    config, _ = lifecycle
    presentation.lock_session(config).close()
    logs = config.root / "quick-logs"
    logs.mkdir()
    supervisor = presentation.Supervisor(config)
    supervisor.state = {
        "version": 1,
        "root": str(config.root),
        "owner": presentation.identity(os.getpid()),
        "owned": {},
        "logs": str(logs),
    }
    child = supervisor.spawn(
        "api_tunnel",
        [
            sys.executable,
            "-u",
            "-c",
            "import time;print('https://fixture-demo.trycloudflare.com',flush=True);time.sleep(100)",
        ],
    )
    try:
        eventually(
            lambda: supervisor.urls.get("api_tunnel") == "https://fixture-demo.trycloudflare.com"
        )
        presentation.cleanup_groups(supervisor.state["owned"], timeout=1)
        child.wait(timeout=3)
        assert not presentation.group_members(supervisor.state["owned"]["api_tunnel"])
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)
        for reader in supervisor.readers:
            reader.join(timeout=2)
        for handler in supervisor.handlers:
            handler.close()


def test_session_log_retention(lifecycle):
    config, start = lifecycle
    folders = config.state_dir / "sessions"
    folders.mkdir(parents=True)
    for index in range(8):
        (folders / f"20000101T000000Z-{index}").mkdir()
    process = start()
    eventually(lambda: serving(config))
    assert len(list(folders.iterdir())) == presentation.KEEP_SESSIONS
    presentation.stop_session(config)
    assert process.wait(timeout=8) == 0


def test_status_uses_session_database_not_other_terminal_environment(lifecycle, monkeypatch):
    config, start = lifecycle
    start()
    eventually(lambda: serving(config))
    monkeypatch.setenv("BEANFEATURE_DATABASE_URL", "sqlite:////nonexistent/other-terminal.sqlite")
    monkeypatch.setattr(presentation, "named_tunnel_running", lambda: False)
    assert presentation.operational_status(config, state(config))["worker"] == "online"


def test_stop_does_not_require_valid_public_url_configuration(lifecycle, monkeypatch):
    config, start = lifecycle
    process = start()
    eventually(lambda: serving(config))
    monkeypatch.setattr(presentation, "ROOT", config.root)
    monkeypatch.setattr(sys, "argv", ["presentation.py", "stop"])
    monkeypatch.setenv("BEANFEATURE_PUBLIC_API_URL", "invalid-public-origin")
    monkeypatch.chdir(config.root)
    assert presentation.main() == 0
    assert process.wait(timeout=8) == 0
    assert_clean(config)


def test_unmanaged_worker_is_rejected_without_killing_it(lifecycle):
    config, _ = lifecycle
    executable = config.root / ".venv/bin/beanfeature-worker"
    executable.parent.mkdir(parents=True)
    executable.write_text("import time;time.sleep(100)")
    (executable.parent / "uvicorn").touch()
    next_script = config.root / "apps/web/node_modules/next/dist/bin/next"
    next_script.parent.mkdir(parents=True)
    next_script.touch()
    worker = subprocess.Popen(
        [sys.executable, str(executable)], cwd=config.root, start_new_session=True
    )
    try:
        with pytest.raises(RuntimeError, match="Unmanaged BeanFeature worker"):
            presentation.Supervisor(config).preflight()
        assert worker.poll() is None
    finally:
        worker.terminate()
        worker.wait(timeout=3)
