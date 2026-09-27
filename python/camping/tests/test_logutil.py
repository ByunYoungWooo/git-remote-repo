"""PII 마스킹 단위 테스트 — NFR-05/NFR-07 강제장치."""
from campbot.core.logutil import mask_pii, mask_phone, mask_rrn


def test_rrn_masked_fully():
    assert "123456-7890123" not in mask_pii("주민번호 123456-7890123 등록")
    assert "[RRN]" in mask_pii("주민번호 123456-7890123 등록")


def test_rrn_without_dash_masked():
    assert "1234567890123" not in mask_pii("rrn:1234567890123")
    assert "[RRN]" in mask_pii("rrn:1234567890123")


def test_phone_last_four_only():
    # NFR-07: 전체 노출 금지 + 마지막 4자리는 표시 허용 (확정 설계)
    out = mask_pii("연락처 010-1234-5678 확인")
    assert "010-1234-5678" not in out   # 전체 번호 비노출
    assert "5678" in out and "***" in out  # 끝자리만 남음


def test_plain_text_untouched():
    text = "사이트 A-02 예약가능, 2026-10-10"
    assert mask_pii(text) == text


def test_rrn_mask_priority_over_phone():
    # RRN(13자리)이 전화번호 패턴과 혼동되지 않아야 함 — RRN 전체 마스킹 확인
    out = mask_pii("rrn 990101-2222333")
    assert "990101-2222333" not in out and "[RRN]" in out


def test_mixed_line_masked_once_each():
    line = "예약자 김OO 010-9876-5432 rrn 311234-5678901 제출 완료"
    out = mask_pii(line)
    assert "311234-5678901" not in out        # RRN 원문 비노출
    assert "[RRN]" in out
    assert "010-9876-5432" not in out          # 전화번호 전체 비노출
    assert "***" in out                        # 마스킹 표시 존재
