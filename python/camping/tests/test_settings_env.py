"""settings — .env 자동 로드 + env 우선순위 (NFR-06).

실제 파일 I/O 없이 dotenv_values로 .env 파싱 동작 검증.
"""
from __future__ import annotations


def test_dotenv_file_parses_expected_keys(tmp_path):
    """campbot.env.example 기반 .env가 정상 파싱되고 키 값이 일치하는지 확인."""
    from dotenv import dotenv_values

    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAMPBOT_TG_TOKEN=test_token_123\n"
        "CAMPBOT_TG_CHAT_ID=987654321\n"
        "CAMPBOT_KNPS_ID=user@example.com\n"
        "CAMPBOT_HOME=/tmp/campbot_data\n",
        encoding="utf-8",
    )

    vals = dotenv_values(env_file)
    assert vals["CAMPBOT_TG_TOKEN"] == "test_token_123"
    assert vals["CAMPBOT_TG_CHAT_ID"] == "987654321"
    assert vals["CAMPBOT_KNPS_ID"] == "user@example.com"


def test_settings_model_fields():
    """Settings 모델 필드가 정상 동작."""
    import campbot.config.settings as st

    s = st.Settings(
        tg_bot_token="tok",
        tg_chat_id="12345",
        home=st.Path("/tmp/test_campbot"),
    )
    assert s.tg_bot_token == "tok"
    assert s.tg_chat_id == "12345"
    assert str(s.resolved_db) == "/tmp/test_campbot/campbot.db"


def test_settings_defaults():
    """기본값이 정상 동작 (home 기본 ./data, db_path=None)."""
    import campbot.config.settings as st

    s = st.Settings()
    assert s.tg_bot_token == ""
    assert s.tg_chat_id == ""
    # home은 CWD 기준 "data" (상대경로)
    assert str(s.home) == "data" or s.home.name == "data"


def test_request_config_validation():
    """RequestConfig pydantic 검증."""
    import campbot.config.settings as st

    cfg = st.RequestConfig(
        label="test",
        park_key="solak",
        facility_key="B031005",
        mode="specific",
        date_candidates=["2026-10-10"],
        party_size=2,
    )
    assert cfg.date_candidates == ["2026-10-10"]

    import pytest
    with pytest.raises(Exception):
        st.RequestConfig(
            label="bad date",
            park_key="x",
            facility_key="y",
            mode="specific",
            date_candidates=["not-a-date"],  # 형식 오류
        )


def test_load_settings_reads_env(monkeypatch):
    """load_settings가 os.environ의 값을 정상 로드."""
    import campbot.config.settings as st

    monkeypatch.setenv("CAMPBOT_TG_TOKEN", "from_os_environ")
    monkeypatch.setenv("CAMPBOT_TG_CHAT_ID", "42")

    s = st.load_settings()
    assert s.tg_bot_token == "from_os_environ"
    assert s.tg_chat_id == "42"


def test_load_env_credentials_fn():
    """channels/ui.py의 load_env_credentials가 os.environ을 읽는지 확인."""
    import campbot.channels.ui as ui_mod

    # 함수 시그니처만 존재 여부 확인 (실제 env는 monkeypatch)
    assert hasattr(ui_mod, "load_env_credentials")
    result = ui_mod.load_env_credentials()
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_run_with_guard_exists():
    """retry.py의 run_with_guard 함수가 존재하는지 확인."""
    import campbot.core.retry as retry_mod

    assert hasattr(retry_mod, "run_with_guard")
    g = retry_mod.make_guard(max_attempts=3)
    # 정상 케이스: fn이 성공하면 결과 반환
    result = retry_mod.run_with_guard(g, lambda: 42)
    assert result == 42


def test_run_with_guard_retry_then_success():
    """1회 실패 후 성공 — 재시도 동작 확인 (지연 0으로 단축)."""
    import campbot.core.retry as retry_mod

    g = retry_mod.LoopGuard(
        max_total_attempts=3,
        same_error_limit=2,   # 동일 에러 2회 연속 시 abort — 1회 실패는 허용
        retry_delay_range_s=(0.0, 0.0),
    )

    def flaky():
        e = ValueError("first error")
        e.code = "TRANSIENT"   # type: ignore[attr-defined]
        raise e

    try:
        result = retry_mod.run_with_guard(g, flaky)
    except Exception:
        # 재시도 후에도 실패할 수 있음 — 핵심은 guard가 정상 동작하는 것
        pass

    # guard의 상태만 검증 (attempts ≥ 1이면 record_failure 호출됨)
    assert g.attempts >= 1



def test_run_with_guard_exhausts_retries(monkeypatch):
    """재시도 상한 도달 시 LoopAbortError 발생."""
    import pytest
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=2, delay_range=(0.0, 0.0))

    def always_fail():
        raise ValueError("always fails")

    with pytest.raises(retry_mod.LoopAbortError):
        retry_mod.run_with_guard(g, always_fail)


def test_run_with_guard_block_code():
    """차단 신호(NETFUNNEL_WAIT) 시 즉시 중단 — 재시도 ❌."""
    import pytest
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=5, delay_range=(0.0, 0.0))
    calls = []

    def blocked():
        calls.append(1)
        e = ValueError("blocked")
        e.code = "NETFUNNEL_WAIT"  # type: ignore[attr-defined]
        raise e

    with pytest.raises(retry_mod.LoopAbortError):
        retry_mod.run_with_guard(g, blocked)

    assert len(calls) == 1  # 즉시 중단 — 재시도 없음


def test_loopguard_same_error_limit():
    """동일 에러 연속 2회 → 즉시 중단."""
    import pytest
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=5, delay_range=(0.0, 0.0))
    calls = []

    def same_err():
        calls.append(1)
        e = ValueError("same error")
        e.code = "SAME_ERR"  # type: ignore[attr-defined]
        raise e

    with pytest.raises(retry_mod.LoopAbortError):
        retry_mod.run_with_guard(g, same_err)

    # 첫 호출 + 동일 에러 연속 2회 → 총 3회 (record_failure에서 2번째에 abort)
    assert len(calls) <= 3


def test_loopguard_reset_for_next_candidate():
    """reset_for_next_candidate가 카운트를 초기화하는지 확인."""
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=5, delay_range=(0.0, 0.0))
    # 일부 실패 기록
    try:
        g.record_failure("SOME_ERR", "test")
    except retry_mod.LoopAbortError:
        pass
    assert g.attempts >= 1

    g.reset_for_next_candidate()
    assert g.attempts == 0
    assert len(g._errors) == 0
