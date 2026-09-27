"""상태 저장 + 락 (DataModel.md v1.0 구현체).

- SQLite 3 (WAL), 스키마 버전 관리
- 파일 락 data/lock — NFR-02 중복 실행 방지, stale 감지는 보고만 하고 자동 삭제 ❌
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
INSERT OR IGNORE INTO schema_version(version) VALUES (1);

CREATE TABLE IF NOT EXISTS request (
    id            INTEGER PRIMARY KEY,
    label         TEXT NOT NULL CHECK(length(label)>0),
    park_key      TEXT NOT NULL,
    facility_key  TEXT NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'specific' CHECK(mode IN ('specific','range')),
    date_candidates TEXT NOT NULL,
    date_from     TEXT,
    date_to       TEXT,
    open_time_local TEXT,
    window_start  TEXT,
    window_end    TEXT,
    party_size    INTEGER NOT NULL DEFAULT 2 CHECK(party_size>=1),
    vehicles      INTEGER NOT NULL DEFAULT 1 CHECK(vehicles>=0),
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK(status IN ('pending','running','success','failed','aborted_hitl')),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at    TEXT,
    UNIQUE(label)
);

CREATE TABLE IF NOT EXISTS request_site (
    id          INTEGER PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES request(id) ON DELETE CASCADE,
    site_key    TEXT NOT NULL CHECK(length(site_key)>0),
    label       TEXT,
    priority    INTEGER NOT NULL CHECK(priority>=1),
    UNIQUE(request_id, priority),
    UNIQUE(request_id, site_key)
);

CREATE TABLE IF NOT EXISTS run (
    id            INTEGER PRIMARY KEY,
    request_id    INTEGER NOT NULL REFERENCES request(id),
    trigger_mode  TEXT NOT NULL DEFAULT 'manual' CHECK(trigger_mode IN ('manual','timer')),
    started_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ended_at      TEXT,
    outcome       TEXT CHECK(outcome IS NULL OR outcome IN
                    ('success','failed','aborted_hitl','crashed','lock_conflict')),
    stage_last    TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT
);

CREATE TABLE IF NOT EXISTS attempt_log (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES run(id),
    seq             INTEGER NOT NULL CHECK(seq>=1),
    stage           TEXT NOT NULL CHECK(stage IN
                    ('login','search','sitelist','priority','booking','hitl','captcha','notify','done')),
    result          TEXT NOT NULL CHECK(result IN ('ok','retry','fatal','wait_human')),
    error_code      TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0 CHECK(retry_count>=0),
    detail          TEXT,
    screenshot_path TEXT,
    html_capture_path TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS reservation_result (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL UNIQUE REFERENCES run(id),
    request_id      INTEGER NOT NULL REFERENCES request(id),
    date_chosen     TEXT NOT NULL,
    site_key        TEXT NOT NULL,
    reservation_no  TEXT,
    status_snapshot TEXT,
    notified_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_request_site_pri ON request_site(request_id, priority);
CREATE INDEX IF NOT EXISTS idx_run_request      ON run(request_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempt_run_seq  ON attempt_log(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_result_request   ON reservation_result(request_id);
"""

STALE_AFTER_S = 30 * 60  # 락 stale 기준 (설정 가능)


class LockConflictError(RuntimeError):
    """다른 실행이 진행 중 — 재실행 거부 (NFR-02)."""


@dataclass(frozen=True)
class StaleLock:
    path: Path
    pid: int
    run_id: int | None
    started_at: str | None
    stale: bool


def db_connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """스키마 v1 적용 (idempotent)."""
    conn.executescript(SCHEMA_V1)
    conn.commit()


# --- 파일 락 -------------------------------------------------------------
class FileLock:
    def __init__(self, lock_path: Path, stale_after_s: float = STALE_AFTER_S) -> None:
        self.path = lock_path
        self.stale_after_s = stale_after_s

    def _read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # 존재는 하는데 kill 불가 → 살았다고 판단

    def acquire(self, run_id: int | None = None) -> bool:
        """획득 시도. 실패면 LockConflictError (stale 여부와 무관 — 보고 후 수동 해제 원칙)."""
        existing = self._read()
        if existing is not None and self._pid_alive(int(existing.get("pid", -1))):
            raise LockConflictError(
                f"진행 중인 실행 감지 (pid={existing.get('pid')}, run_id={existing.get('run_id')}) — "
                "중복 실행 거부. 확인 후 `cli lock-release` 사용."
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(
                    {"pid": os.getpid(), "run_id": run_id,
                     "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                    f,
                )
            return True
        except Exception:
            self.path.unlink(missing_ok=True)
            raise

    def release(self) -> None:
        # 자기 pid만 삭제 (보수적)
        existing = self._read()
        if existing is not None and int(existing.get("pid", -1)) == os.getpid():
            self.path.unlink(missing_ok=True)

    def inspect_stale(self) -> StaleLock | None:
        """기동 점검용 (NFR-08): stale 감지 → 보고, 자동 삭제 ❌."""
        existing = self._read()
        if existing is None:
            return None
        pid = int(existing.get("pid", -1))
        alive = self._pid_alive(pid)
        started = existing.get("started_at")
        stale = not alive  # 시작 시각 비교는 표시 정보만 (UTC 파싱 단순화)
        return StaleLock(self.path, pid, existing.get("run_id"), started, stale)

    def force_release(self) -> None:
        """cli lock-release 전용 — 형(운영자) 확인 후 명시 호출."""
        self.path.unlink(missing_ok=True)


@contextmanager
def locked(lock_path: Path, run_id: int | None = None):
    lk = FileLock(lock_path)
    try:
        lk.acquire(run_id)
    except LockConflictError:
        raise
    try:
        yield lk
    finally:
        lk.release()
