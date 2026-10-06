"""settings — .env 자동 로드 + Settings 모델 필드 (NFR-06).

run_with_guard 상세 시나리오는 test_retry.py에서 이미 검증됨.
여기서는 settings + dotenv 파싱만 확인.
"""
from __future__ import annotations


def test_dotenv_file_parses_expected_keys(tmp_path):
    """campbot.env.example 기반 .env가 정상 파싱되는지 확인."""
    from dotenv import dotenv_values

    env_file = tmp_path / ".env"
    # NOTE: 값에 "TEST"가 포함되면 보안 마스킹이 활성화되어 파싱 결과가 ***로 대체됨.
    env_file.write_text(
        "CAMPBOT_TG_TOKEN=abc123xyz_987654321\n"
        "CAMPBOT_TG_CHAT_ID=chatid_000000\n"
        "CAMPBOT_KNPS_ID=user@example.com\n"
        "CAMPBOT_HOME=/tmp/campbot_data\n",
        encoding="utf-8",
    )

    vals = dotenv_values(env_file)
    assert vals["CAMPBOT_TG_TOKEN"] == "abc123xyz_987654321"
    assert vals["CAMPBOT_TG_CHAT_ID"] == "chatid_000000"
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
    """기본값이 정상 동작."""
    import campbot.config.settings as st

    s = st.Settings()
    assert s.tg_bot_token == ""
    assert s.tg_chat_id == ""


def test_request_config_validation():
    """RequestConfig pydantic 검증."""
    import pytest
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

    with pytest.raises(Exception):
        st.RequestConfig(
            label="bad date",
            park_key="x",
            facility_key="y",
            mode="specific",
            date_candidates=["not-a-date"],
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
    """channels/ui.py의 load_env_credentials가 정상 동작."""
    import campbot.channels.ui as ui_mod

    result = ui_mod.load_env_credentials()
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_run_with_guard_exists_and_success():
    """run_with_guard — 성공 케이스만 확인 (실패 시나리오는 test_retry.py)."""
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=3, delay_range=(0.0, 0.0))
    result = retry_mod.run_with_guard(g, lambda: 42)
    assert result == 42


def test_run_with_guard_exhausts_retries():
    """재시도 상한 도달 시 LoopAbortError (차단코드 아님 — 동일 에러)."""
    import pytest
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=3, delay_range=(0.0, 0.0))
    # same_error_limit=2 → 2번째 호출에 abort. max_total은 3이지만 동일 에러가 먼저 도달.
    calls = []

    def always_fail():
        calls.append(1)
        e = ValueError("always fails")
        raise e

    with pytest.raises(retry_mod.LoopAbortError):
        retry_mod.run_with_guard(g, always_fail)


def test_run_with_guard_block_code_immediate_abort():
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

    with pytest.raises(retry_mod.LoopAbortError, match="차단"):
        retry_mod.run_with_guard(g, blocked)

    assert len(calls) == 1  # 즉시 중단 — 재시도 없음


def test_loopguard_reset_for_next_candidate():
    """reset_for_next_candidate가 카운트를 초기화하는지 확인."""
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=5, delay_range=(0.0, 0.0))
    try:
        g.record_failure("SOME_ERR", "test")
    except retry_mod.LoopAbortError:
        pass
    assert g.attempts >= 1

    g.reset_for_next_candidate()
    assert g.attempts == 0
    assert len(g._errors) == 0


def test_loopguard_same_error_limit_two():
    """동일 에러 연속 2회 → 즉시 중단 (기본 same_error_limit=2)."""
    import pytest
    import campbot.core.retry as retry_mod

    g = retry_mod.make_guard(max_attempts=5, delay_range=(0.0, 0.0))
    calls = []

    def same_err():
        calls.append(1)
        e = ValueError("same error")
        e.code = "SAME_ERR"  # type: ignore[attr-defined]
        raise e

    with pytest.raises(retry_mod.LoopAbortError, match="동일 에러"):
        retry_mod.run_with_guard(g, same_err)

    assert len(calls) == 2  # 1회 + 2번째에 abort


def test_loopguard_block_codes_frozenset():
    """block_codes가 NETFUNNEL_WAIT와 IP_SUSPECTED를 포함하는지 확인."""
    import campbot.core.retry as retry_mod

    g = retry_mod.LoopGuard()
    assert "NETFUNNEL_WAIT" in g.block_codes
    assert "IP_SUSPECTED" in g.block_codes
