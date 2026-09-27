"""state(SQLite 스키마 + 락) 단위 테스트 — DataModel.md §7 S-1~S-5 매핑."""
import pytest

from campbot.core import state


@pytest.fixture()
def conn(tmp_path):
    c = state.db_connect(tmp_path / "campbot.db")
    state.init_schema(c)
    yield c
    c.close()


def test_schema_version_applied(conn):
    row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert row[0] == 1


def test_idempotent_reinit(conn, tmp_path):
    # 재기동 시에도 같은 DDL 반복 적용 가능 (DataModel §6)
    state.init_schema(conn)
    state.init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert {"request", "request_site", "run", "attempt_log", "reservation_result"} <= tables


def test_request_and_priority_sites(conn):
    cur = conn.execute(
        "INSERT INTO request(label, park_key, facility_key, date_candidates)"
        " VALUES ('설악 10월','solak','camp1','[\"2026-10-10\",\"2026-10-17\"]')"
    )
    rid = cur.lastrowid
    for i, key in enumerate(["A-01", "A-02", "B-01"], start=1):
        conn.execute(
            "INSERT INTO request_site(request_id, site_key, priority) VALUES (?,?,?)",
            (rid, key, i),
        )
    ordered = [r[0] for r in conn.execute(
        "SELECT site_key FROM request_site WHERE request_id=? ORDER BY priority", (rid,))]
    assert ordered == ["A-01", "A-02", "B-01"]


def test_duplicate_site_in_request_rejected(conn):
    rid = conn.execute(
        "INSERT INTO request(label,park_key,facility_key,date_candidates) VALUES ('x','p','f','[]')"
    ).lastrowid
    conn.execute("INSERT INTO request_site(request_id,site_key,priority) VALUES (?,?,1)", (rid, "A-01"))
    with pytest.raises(Exception):  # UNIQUE(request_id, site_key) — sqlite3.IntegrityError
        conn.execute("INSERT INTO request_site(request_id,site_key,priority) VALUES (?,?,2)", (rid, "A-01"))


def test_run_attempt_and_result_flow(conn):
    rid = conn.execute(
        "INSERT INTO request(label,park_key,facility_key,date_candidates) VALUES ('r','p','f','[\"2026-10-10\"]')"
    ).lastrowid
    run_id = conn.execute("INSERT INTO run(request_id) VALUES (?)", (rid,)).lastrowid
    for i in range(3):
        conn.execute(
            "INSERT INTO attempt_log(run_id,seq,stage,result,error_code)"
            " VALUES (?,?,?,?,'SITE_TAKEN')",
            (run_id, i + 1, "sitelist", "retry" if i < 2 else "fatal"),
        )
    # S-4: 한 run당 result 최대 1건 (멱등성 NFR-02)
    conn.execute(
        "INSERT INTO reservation_result(run_id,request_id,date_chosen,site_key)"
        " VALUES (?,?,?,?)", (run_id, rid, "2026-10-10", "A-02")
    )
    with pytest.raises(Exception):  # UNIQUE run_id — sqlite3.IntegrityError
        conn.execute(
            "INSERT INTO reservation_result(run_id,request_id,date_chosen,site_key)"
            " VALUES (?,?,?,?)", (run_id, rid, "2026-10-17", "B-01")
    )


def test_file_lock_conflict_and_stale(tmp_path):
    lockfile = tmp_path / "data" / "lock"
    lk1 = state.FileLock(lockfile)
    assert lk1.acquire(run_id=101) is True

    # S-5a: 같은 락 재획득 거부 (pid 생존 중)
    with pytest.raises(state.LockConflictError):
        state.FileLock(lockfile).acquire()

    # S-5b: stale 감지는 보고만, 자동 삭제 ❌
    lk1._read()["pid"] = 999_999  # 사망한 pid로 위조 (테스트용)
    lockfile.write_text(__import__("json").dumps(
        {"pid": 999_999, "run_id": 101, "started_at": "2026-09-27T08:00:00Z"}))
    stale = state.FileLock(lockfile).inspect_stale()
    assert stale is not None and stale.stale and stale.run_id == 101
    assert lockfile.exists(), "stale 락은 자동 삭제되면 안 됨 (NFR-08: 보고 후 수동 해제)"

    # 명시적 force_release 만이 삭제 가능 (cli lock-release 대응)
    state.FileLock(lockfile).force_release()
    assert not lockfile.exists()
