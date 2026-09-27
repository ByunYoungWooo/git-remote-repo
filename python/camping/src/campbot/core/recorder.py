"""recorder — 실행·시도 기록 추상화 (FR-015 전량 로깅, NFR-05).

의존 방향: orchestrator → Recorder(인터페이스) → InMemoryRecorder(테스트) / SqliteRecorder(운영)
"""
from __future__ import annotations

import abc
import sqlite3
import time
from typing import Any


class Recorder(abc.ABC):
    @abc.abstractmethod
    def begin_run(self, request_id: int | None = None, trigger_mode: str = "manual") -> int: ...

    @abc.abstractmethod
    def record_attempt(
        self,
        stage: str,
        result: str,                 # ok|retry|fatal|wait_human (attempt_log CHECK와 일치)
        error_code: str | None = None,
        detail: str = "",
        retry_count: int = 0,
    ) -> None: ...

    @abc.abstractmethod
    def record_result(
        self, date_chosen: str, site_key: str, reservation_no: str = ""
    ) -> None: ...

    @abc.abstractmethod
    def finish_run(self, outcome: str, last_error: str = "") -> None: ...


class InMemoryRecorder(Recorder):
    """테스트용 — 기록을 리스트로 쌓아 어설션."""

    def __init__(self) -> None:
        self.run_id = 0
        self.attempts: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None
        self.outcome: str | None = None
        self.last_error = ""

    def begin_run(self, request_id=None, trigger_mode="manual") -> int:
        self.run_id += 1
        return self.run_id

    def record_attempt(self, stage, result, error_code=None, detail="", retry_count=0) -> None:
        self.attempts.append(
            {"stage": stage, "result": result, "error_code": error_code,
             "detail": detail, "retry_count": retry_count}
        )

    def record_result(self, date_chosen, site_key, reservation_no="") -> None:
        self.result = {
            "date_chosen": date_chosen, "site_key": site_key, "reservation_no": reservation_no,
            "ts": time.time(),
        }

    def finish_run(self, outcome, last_error="") -> None:
        self.outcome = outcome
        self.last_error = last_error


class SqliteRecorder(Recorder):
    """운영용 — DataModel.md 스키마에 기록 (core.state 연결)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        assert hasattr(conn, "execute"), "sqlite3.Connection 필요"
        self.conn = conn
        self.run_id: int | None = None

    def begin_run(self, request_id=None, trigger_mode="manual") -> int:
        cur = self.conn.execute(
            "INSERT INTO run(request_id, trigger_mode) VALUES (?, ?)", (request_id, trigger_mode)
        )
        self.run_id = cur.lastrowid
        return self.run_id

    def record_attempt(self, stage, result, error_code=None, detail="", retry_count=0) -> None:
        seq = len(
            self.conn.execute("SELECT id FROM attempt_log WHERE run_id=?", (self.run_id,)).fetchall()
        ) + 1
        self.conn.execute(
            "INSERT INTO attempt_log(run_id,seq,stage,result,error_code,retry_count,detail)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.run_id, seq, stage, result, error_code, retry_count, detail),
        )

    def record_result(self, date_chosen, site_key, reservation_no="") -> None:
        req = self.conn.execute(
            "SELECT request_id FROM run WHERE id=?", (self.run_id,)
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO reservation_result(run_id,request_id,date_chosen,site_key,reservation_no)"
            " VALUES (?,?,?,?,?)",
            (self.run_id, req, date_chosen, site_key, reservation_no),
        )

    def finish_run(self, outcome, last_error="") -> None:
        self.conn.execute(
            "UPDATE run SET ended_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'),"
            "outcome=?,last_error=? WHERE id=?",
            (outcome, last_error or None, self.run_id),
        )
