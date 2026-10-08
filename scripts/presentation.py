#!/usr/bin/env python3
"""Foreground presentation supervisor. Runtime state stays local; no scientific writes here."""

import argparse
import fcntl
import json
import logging
import math
import os
import platform
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event, Thread
from urllib.parse import urlsplit

import psutil
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
LOG_BYTES = 1024 * 1024
KEEP_SESSIONS = 5


@dataclass
class Config:
    root: Path
    quick: bool = False
    local_api: str = "http://127.0.0.1:8000"
    local_web: str = "http://127.0.0.1:3000"
    public_api: str = "https://api.fwor1d.ru"
    public_web: str = "https://beanfeature.fwor1d.ru"
    startup_timeout: float = 60
    check_interval: float = 5
    public_interval: float = 30
    shutdown_timeout: float = 10

    @property
    def state_dir(self) -> Path:
        return self.root / "storage/presentation"

    @property
    def db_path(self) -> Path:
        url = make_url(
            os.getenv("BEANFEATURE_DATABASE_URL", "sqlite:///storage/sqlite/beanfeature.sqlite")
        )
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            raise RuntimeError("Presentation requires the existing file-based SQLite configuration")
        if url.query:
            raise RuntimeError("Presentation expects a plain file-based SQLite URL")
        path = Path(url.database)
        return path if path.is_absolute() else self.root / path


def identity(pid: int) -> dict:
    return {"pid": pid, "created": psutil.Process(pid).create_time()}


def alive(record: dict | None) -> bool:
    if not record:
        return False
    try:
        process = psutil.Process(record["pid"])
        return (
            process.create_time() == record["created"] and process.status() != psutil.STATUS_ZOMBIE
        )
    except (psutil.Error, KeyError, TypeError):
        return False


def group_members(record: dict) -> list[psutil.Process]:
    """Validate birth time before touching a group, including an orphaned group."""
    pid = record["pid"]
    try:
        if psutil.Process(pid).create_time() != record["created"]:
            return []  # Reused leader PID: never signal this new group.
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        return []
    members = []
    for process in psutil.process_iter():
        try:
            if (
                os.getpgid(process.pid) == pid
                and os.getsid(process.pid) == pid
                and process.create_time() >= record["created"]
                and process.status() != psutil.STATUS_ZOMBIE
            ):
                members.append(process)
        except (OSError, psutil.Error):
            continue
    return members


def cleanup_groups(records: dict, timeout: float = 10) -> None:
    groups = list(reversed(list(records.values())))
    for record in groups:
        if group_members(record):
            try:
                os.killpg(record["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and any(group_members(record) for record in groups):
        time.sleep(0.1)
    for record in groups:
        if group_members(record):
            try:
                os.killpg(record["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass


def read_state(config: Config) -> dict:
    try:
        state = json.loads((config.state_dir / "session.json").read_text())
        if state.get("root") != str(config.root) or state.get("version") != 1:
            raise RuntimeError("Unrecognized presentation state; inspect storage/presentation")
        records = [state.get("owner"), *state.get("owned", {}).values()]
        for record in records:
            if (
                not isinstance(record, dict)
                or type(record.get("pid")) is not int
                or record["pid"] <= 1
                or type(record.get("created")) not in (int, float)
                or not math.isfinite(record["created"])
                or record["created"] <= 0
            ):
                raise RuntimeError(
                    "Invalid process identity in presentation state; inspect it manually"
                )
        return state
    except FileNotFoundError:
        return {}
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("Invalid presentation state; inspect storage/presentation") from exc


def save_state(config: Config, state: dict) -> None:
    temporary = config.state_dir / "session.json.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(config.state_dir / "session.json")


def lock_session(config: Config):
    config.state_dir.mkdir(parents=True, exist_ok=True)
    handle = (config.state_dir / "session.lock").open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def probe(url: str, application: str, *, read_only: bool = False) -> str:
    # System curl uses the host TLS trust store (Python.org builds on macOS may not).
    # No shell, no -k, bounded body/time, and no exception/credential details in status.
    try:
        response = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "2",
                "--max-time",
                "3",
                "--max-filesize",
                "16384",
                "--header",
                "Cache-Control: no-cache",
                "--write-out",
                "\n%{http_code}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if response.returncode:
            return {28: "timeout", 60: "tls_error", 63: "unexpected_response"}.get(
                response.returncode, "unreachable"
            )
        payload, code = response.stdout.rsplit("\n", 1)
        if code != "200":
            return f"http_{code}"
        body = json.loads(payload)
        if (
            body.get("application") == application
            and body.get("status") == "ready"
            and (not read_only or body.get("read_only") is True)
        ):
            return "ready"
        return "unexpected_response"
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError:
        return "unreachable"
    except (ValueError, AttributeError):
        return "unexpected_response"


def public_probes(state: dict) -> dict:
    with ThreadPoolExecutor(max_workers=2) as pool:
        api = pool.submit(probe, state["public_api"] + "/ready", "beanfeature-api", read_only=True)
        web = pool.submit(probe, state["public_web"] + "/api/ready", "beanfeature-web")
        return {"api": api.result(), "web": web.result()}


def named_tunnel_running() -> bool | None:
    # The root-owned launchd service may deny cmdline access. Never print its arguments.
    try:
        processes = subprocess.run(
            ["ps", "-axo", "pid=,comm="], capture_output=True, text=True, timeout=3, check=True
        )
        for line in processes.stdout.splitlines():
            fields = line.split(maxsplit=1)
            if len(fields) == 2 and Path(fields[1]).name == "cloudflared":
                args = subprocess.run(
                    ["ps", "-p", fields[0], "-o", "args="],
                    capture_output=True,
                    text=True,
                    timeout=3,
                ).stdout
                if re.search(r"\btunnel\s+(?:.*\s)?run\b", args):
                    return True
        return False
    except (OSError, subprocess.SubprocessError):
        return None  # Introspection failure is not a local application failure.


def heartbeat(config: Config, worker: dict | None, *, database: Path | None = None) -> str:
    if not alive(worker):
        return "offline"
    try:
        with sqlite3.connect(
            (database or config.db_path).as_uri() + "?mode=ro", uri=True, timeout=2
        ) as connection:
            row = connection.execute("SELECT seen_at FROM worker_heartbeat WHERE id=1").fetchone()
        if not row:
            return "stale"
        seen = datetime.fromisoformat(row[0]).replace(tzinfo=UTC).timestamp()
        age = time.time() - seen
        return "online" if seen >= worker["created"] and 0 <= age < 20 else "stale"
    except (sqlite3.Error, ValueError):
        return "unknown"


def operational_status(config: Config, state: dict, *, public: bool = True) -> dict:
    owned = state.get("owned", {})
    running = alive(state.get("owner"))
    stopped = state.get("phase") in {"stopped", "failed"} and not running
    result = {"session": state.get("phase", "stopped") if running or stopped else "orphaned"}
    for name, url, app in (
        ("api", state.get("local_api", config.local_api) + "/ready", "beanfeature-api"),
        ("web", state.get("local_web", config.local_web) + "/api/ready", "beanfeature-web"),
    ):
        result[name] = (
            probe(url, app, read_only=name == "api") if alive(owned.get(name)) else "offline"
        )
    result["worker"] = (
        "stopped"
        if stopped
        else heartbeat(
            config,
            owned.get("worker"),
            database=Path(state["database"]) if state.get("database") else None,
        )
    )
    result["sleep"] = "active" if alive(owned.get("sleep")) else "inactive"
    if state.get("mode") == "quick":
        result["tunnel"] = (
            "running"
            if all(alive(owned.get(n)) for n in ("api_tunnel", "web_tunnel"))
            else "offline"
        )
    else:
        detected = named_tunnel_running()
        result["tunnel"] = (
            "unknown" if detected is None else "external_process" if detected else "offline"
        )
    result["public"] = (
        public_probes(state)
        if public and state.get("public_api") and state.get("public_web")
        else state.get("public", {})
    )
    if state.get("failure"):
        result["failure"] = state["failure"]
    if state.get("logs"):
        result["logs"] = state["logs"]
    return result


def show_status(config: Config) -> dict:
    state = read_state(config)
    if not state:
        state = {"phase": "stopped"}
    result = operational_status(config, state)
    print(json.dumps(result, indent=2))
    return result


def stop_session(config: Config) -> None:
    lock = lock_session(config)
    if lock is not None:
        try:
            state = read_state(config)
            cleanup_groups(state.get("owned", {}), config.shutdown_timeout)
            if state:
                state["phase"] = "stopped"
                save_state(config, state)
            print("Presentation stopped. External Named Tunnel remains managed by macOS.")
        finally:
            lock.close()
        return
    state = read_state(config)
    if not alive(state.get("owner")):
        raise RuntimeError("Session lock is held but its owner is unavailable; retry stop")
    os.kill(state["owner"]["pid"], signal.SIGTERM)
    deadline = time.monotonic() + config.shutdown_timeout + 10
    while time.monotonic() < deadline:
        lock = lock_session(config)
        if lock is not None:
            lock.close()
            print("Presentation stopped. External Named Tunnel remains managed by macOS.")
            return
        time.sleep(0.2)
    raise RuntimeError("Supervisor did not stop in time; inspect session logs before retrying")


def port_conflict(port: int, root: Path = ROOT) -> None:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen()
        except OSError as exc:
            listeners = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.split()
            roles = []
            for pid in listeners:
                try:
                    process = psutil.Process(int(pid))
                    args = process.cmdline()
                    beanfeature = any("beanfeature_api" in a for a in args) or (
                        process.name().startswith("next-server")
                        and Path(process.cwd()) == root / "apps/web"
                    )
                    role = (
                        "unmanaged BeanFeature candidate"
                        if beanfeature
                        else "unrelated/unidentified process"
                    )
                    roles.append(f"PID {pid} ({role})")
                except psutil.Error:
                    roles.append(f"PID {pid} (unidentified process)")
            raise RuntimeError(
                f"Port {port} is occupied: {', '.join(roles) or 'unidentified listener'}. "
                "Stop it explicitly; no process was killed."
            ) from exc


class Supervisor:
    def __init__(self, config: Config):
        self.config = config
        self.stop = Event()
        self.children: dict[str, subprocess.Popen] = {}
        self.readers: list[Thread] = []
        self.handlers: list[RotatingFileHandler] = []
        self.urls: dict[str, str] = {}
        self.state: dict = {}

    def publish(self) -> None:
        save_state(self.config, self.state)

    def log(self, name: str) -> logging.Logger:
        logger = logging.Logger(f"presentation.{name}", logging.INFO)
        handler = RotatingFileHandler(
            Path(self.state["logs"]) / f"{name}.log", maxBytes=LOG_BYTES, backupCount=1
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        self.handlers.append(handler)
        return logger

    def spawn(
        self, name: str, command: list[str], *, cwd: Path | None = None, env: dict | None = None
    ) -> subprocess.Popen:
        logger = self.log(name)
        child = subprocess.Popen(
            command,
            cwd=cwd or self.config.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
        )
        self.children[name] = child
        self.state["owned"][name] = identity(child.pid)
        self.publish()

        def output() -> None:
            assert child.stdout is not None
            pending = ""
            while chunk := child.stdout.read1(4096):
                text = chunk.decode(errors="replace")
                logger.info(text.rstrip())
                pending = (pending + text)[-8192:]
                found = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", pending)
                if found:
                    self.urls[name] = found[0]
            child.stdout.close()

        thread = Thread(target=output, daemon=True, name=f"presentation-log-{name}")
        thread.start()
        self.readers.append(thread)
        return child

    def ensure_alive(self) -> None:
        if self.stop.is_set():
            raise InterruptedError("Presentation stop requested")
        for name, child in self.children.items():
            if child.poll() is not None:
                raise RuntimeError(f"{name} exited (code {child.returncode}); inspect {name}.log")

    def wait(self, label: str, condition) -> None:
        deadline = time.monotonic() + self.config.startup_timeout
        while time.monotonic() < deadline:
            self.ensure_alive()
            if condition():
                return
            self.stop.wait(0.3)
        raise RuntimeError(f"{label} readiness timed out; inspect session logs")

    def preflight(self) -> None:
        config = self.config
        for binary in ("node", "npm", "lsof", "curl"):
            if not shutil.which(binary):
                raise RuntimeError(f"Missing {binary}; run make setup")
        for binary in ("uvicorn", "beanfeature-worker"):
            if not (config.root / ".venv/bin" / binary).is_file():
                raise RuntimeError("Incomplete .venv; run make setup")
        if not (config.root / "apps/web/node_modules/next/dist/bin/next").is_file():
            raise RuntimeError("Missing Next.js; run make setup")
        if platform.system() == "Darwin" and not Path("/usr/bin/caffeinate").is_file():
            raise RuntimeError("macOS caffeinate is unavailable")
        if config.quick and not shutil.which("cloudflared"):
            raise RuntimeError("Quick mode requires cloudflared")
        for url in (config.local_api, config.local_web):
            port_conflict(urlsplit(url).port, config.root)
        # One worker per existing runtime. Refuse to adopt/duplicate an unmanaged worker.
        for process in psutil.process_iter():
            try:
                args = process.cmdline()
                if any(
                    Path(a).name == "beanfeature-worker"
                    or a == "beanfeature_worker.main"
                    or a.endswith("/beanfeature_worker/main.py")
                    for a in args
                ):
                    same = str(config.root) in " ".join(args) or Path(process.cwd()) == config.root
                    if same:
                        raise RuntimeError(
                            f"Unmanaged BeanFeature worker PID {process.pid}; stop it explicitly"
                        )
            except (psutil.Error, OSError):
                continue
        with sqlite3.connect(config.db_path.as_uri() + "?mode=ro", uri=True) as connection:
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        head = ScriptDirectory(
            str(config.root / "packages/infrastructure/alembic")
        ).get_current_head()
        if revision != [(head,)]:
            raise RuntimeError(
                "SQLite schema is incompatible; run make migrate deliberately before presentation"
            )

    def environment(self) -> dict:
        env = os.environ.copy()
        env.update(
            BEANFEATURE_DEMO_READ_ONLY="1",
            NEXT_PUBLIC_DEMO_READ_ONLY="1",
            NEXT_PUBLIC_API_BASE_URL="" if self.config.quick else self.config.public_api,
            BEANFEATURE_INTERNAL_API_BASE_URL=self.config.local_api,
            BEANFEATURE_CORS_ORIGINS=f"{self.config.public_web},http://127.0.0.1:3000,http://localhost:3000",
        )
        return env

    def build(self) -> None:
        root = self.config.root
        web = root / "apps/web"
        paths = [
            web / name
            for name in ("package.json", "package-lock.json", "next.config.ts", "tsconfig.json")
        ]
        paths.extend(p for p in (web / "src").rglob("*") if p.is_file() and p.name != ".DS_Store")
        digest = sha256(
            json.dumps(
                {"api": self.environment()["NEXT_PUBLIC_API_BASE_URL"], "read_only": True}
            ).encode()
        )
        for path in sorted(paths):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
        stamp = web / ".next/beanfeature-named-build.sha256"
        build_id = web / ".next/BUILD_ID"
        expected = (
            f"{digest.hexdigest()} {build_id.read_text().strip()}" if build_id.exists() else ""
        )
        if expected and stamp.exists() and stamp.read_text().strip() == expected:
            print("Using current production Web build.", flush=True)
            return
        print("Building production Web; see session build.log.", flush=True)
        child = self.spawn("build", ["npm", "run", "build"], cwd=web, env=self.environment())
        while child.poll() is None:
            if self.stop.wait(0.2):
                raise InterruptedError("Stop requested during build")
            for name, other in self.children.items():
                if name != "build" and other.poll() is not None:
                    raise RuntimeError(f"{name} exited during build")
        if child.returncode != 0:
            raise RuntimeError("Web build failed; inspect build.log")
        del self.children["build"]
        # Keep its group record until cleanup in case the build left a descendant.
        stamp.write_text(f"{digest.hexdigest()} {build_id.read_text().strip()}\n")

    def start_components(self) -> None:
        config = self.config
        env = self.environment()
        if platform.system() == "Darwin":
            self.spawn("sleep", ["/usr/bin/caffeinate", "-i", "-s", "-w", str(os.getpid())])
        else:
            print("Sleep protection unavailable on this non-macOS host.", flush=True)
        self.build()
        self.spawn(
            "api",
            [
                str(config.root / ".venv/bin/uvicorn"),
                "beanfeature_api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(urlsplit(config.local_api).port),
                "--no-access-log",
            ],
            env=env,
        )
        self.wait(
            "API",
            lambda: (
                probe(config.local_api + "/ready", "beanfeature-api", read_only=True) == "ready"
            ),
        )
        self.spawn("worker", [str(config.root / ".venv/bin/beanfeature-worker")], env=env)
        self.wait(
            "worker heartbeat", lambda: heartbeat(config, self.state["owned"]["worker"]) == "online"
        )
        self.spawn(
            "web",
            [
                "node",
                "node_modules/next/dist/bin/next",
                "start",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(urlsplit(config.local_web).port),
            ],
            cwd=config.root / "apps/web",
            env=env,
        )
        self.wait(
            "Web/backend",
            lambda: probe(config.local_web + "/api/ready", "beanfeature-web") == "ready",
        )
        if config.quick:
            for name, local in (("api_tunnel", config.local_api), ("web_tunnel", config.local_web)):
                self.spawn(name, ["cloudflared", "tunnel", "--protocol", "http2", "--url", local])
                self.wait(name, lambda name=name: name in self.urls)
            self.state.update(
                public_api=self.urls["api_tunnel"], public_web=self.urls["web_tunnel"]
            )

    def run(self) -> int:
        lock = lock_session(self.config)
        if lock is None:
            result = show_status(self.config)
            if (
                result["session"] == "serving"
                and all(result[n] == "ready" for n in ("api", "web"))
                and result["worker"] == "online"
            ):
                print(
                    "This presentation session is already serving; no duplicate processes started."
                )
                return 0
            raise RuntimeError(
                "Presentation session is already starting, stopping or unhealthy; inspect status"
            )
        previous_handlers = {}
        try:
            previous = read_state(self.config)
            cleanup_groups(previous.get("owned", {}), self.config.shutdown_timeout)
            sessions = self.config.state_dir / "sessions"
            sessions.mkdir(exist_ok=True)
            for old in sorted(sessions.iterdir())[: -(KEEP_SESSIONS - 1)]:
                if old.is_dir() and not old.is_symlink():
                    shutil.rmtree(old)
            logs = sessions / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{os.getpid()}"
            logs.mkdir()
            self.state = {
                "version": 1,
                "root": str(self.config.root),
                "owner": identity(os.getpid()),
                "owned": {},
                "phase": "starting",
                "mode": "quick" if self.config.quick else "named",
                "logs": str(logs),
                "database": str(self.config.db_path),
                "local_api": self.config.local_api,
                "local_web": self.config.local_web,
                "public_api": "" if self.config.quick else self.config.public_api,
                "public_web": "" if self.config.quick else self.config.public_web,
            }
            self.publish()
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.signal(
                    signum, lambda _sig, _frame: self.stop.set()
                )
            self.preflight()
            self.start_components()
            self.ensure_alive()
            self.state["phase"] = "serving"
            self.publish()
            print(
                f"Local presentation READY: {self.config.local_web}\n"
                f"Public: {self.state['public_web']}\nLogs: {logs}\n"
                "Ctrl-C or make presentation-stop to stop.",
                flush=True,
            )
            local_at = public_at = 0.0
            failures = 0
            last_public = None
            while not self.stop.wait(0.3):
                self.ensure_alive()
                now = time.monotonic()
                if now >= local_at:
                    status = operational_status(self.config, self.state, public=False)
                    if status["worker"] != "online":
                        raise RuntimeError(f"Worker heartbeat is {status['worker']}")
                    failures = (
                        failures + 1 if any(status[n] != "ready" for n in ("api", "web")) else 0
                    )
                    if failures >= 3:
                        raise RuntimeError("API/Web readiness failed three consecutive checks")
                    local_at = now + self.config.check_interval
                if now >= public_at:
                    self.state["public"] = public_probes(self.state)
                    self.state["tunnel"] = operational_status(
                        self.config, self.state, public=False
                    )["tunnel"]
                    public = (self.state["tunnel"], self.state["public"])
                    if public != last_public:
                        connected = self.state["tunnel"] in {"external_process", "running"} and all(
                            v == "ready" for v in self.state["public"].values()
                        )
                        print(
                            f"Public {'READY' if connected else 'DEGRADED'}: "
                            f"tunnel={public[0]}, probes={public[1]}",
                            flush=True,
                        )
                        last_public = public
                    self.publish()
                    public_at = now + self.config.public_interval
            return 0
        except InterruptedError:
            return 0
        except Exception as exc:
            if self.state:
                self.state["failure"] = str(exc)
            diagnostics = f"\nLogs: {self.state['logs']}" if self.state else ""
            print(f"ERROR: {exc}{diagnostics}", file=sys.stderr, flush=True)
            return 1
        finally:
            if self.state:
                self.state["phase"] = "stopping"
                try:
                    self.publish()
                except OSError as exc:
                    print(
                        f"Could not persist stopping state: {type(exc).__name__}", file=sys.stderr
                    )
                components = {
                    name: record for name, record in self.state["owned"].items() if name != "sleep"
                }
                cleanup_groups(components, self.config.shutdown_timeout)
                cleanup_groups(
                    {"sleep": self.state["owned"]["sleep"]}
                    if "sleep" in self.state["owned"]
                    else {},
                    1,
                )
                for child in self.children.values():
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
                for reader in self.readers:
                    reader.join(timeout=2)
                for handler in self.handlers:
                    handler.close()
                self.state["phase"] = "failed" if self.state.get("failure") else "stopped"
                try:
                    self.publish()
                except OSError as exc:
                    print(f"Could not persist final state: {type(exc).__name__}", file=sys.stderr)
                print(
                    "Owned presentation processes stopped; external Named Tunnel unchanged.",
                    flush=True,
                )
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
            lock.close()


def public_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError(
            "Public presentation URL must be an HTTPS origin without credentials or query"
        )
    return value.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop"))
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Own two emergency Quick Tunnels instead of using external Named Tunnel",
    )
    args = parser.parse_args()
    config = Config(root=ROOT, quick=args.quick)
    os.chdir(config.root)
    try:
        if args.action == "start":
            config.public_api = public_url(
                os.getenv("BEANFEATURE_PUBLIC_API_URL", config.public_api)
            )
            config.public_web = public_url(
                os.getenv("BEANFEATURE_PUBLIC_WEB_URL", config.public_web)
            )
            return Supervisor(config).run()
        if args.action == "stop":
            stop_session(config)
            return 0
        result = show_status(config)
        local = (
            result["session"] == "serving"
            and result["api"] == result["web"] == "ready"
            and result["worker"] == "online"
        )
        public = (
            result["tunnel"] in {"external_process", "running"}
            and result["public"]
            and all(v == "ready" for v in result["public"].values())
        )
        return (
            0
            if local and public and (platform.system() != "Darwin" or result["sleep"] == "active")
            else 1
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Presentation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
