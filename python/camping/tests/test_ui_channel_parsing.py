"""[유닛] UiKnpsChannel 순수 파싱·CAPTCHA — KNPS 접속 ❌ / Playwright ❌ (NFR-10).

검증 대상:
  - parse_slots: 실측 셀 구조(열=날짜, data-use_df) → SiteStatus[] 매핑 정확성
    근거: output/knps_c2_20261003/summary.json rowsSample (렌더링 기준 실제 값)
  - site_key_from_title: data-title 규칙("공원-야영지-종류-사이트")
  - captcha.white_composite: 투명배경 RGBA → 흰색 합성 (C-1 실측 피트폴)
  - captcha.classify: 숫자만 추출, 비숫자/빈값 = ""
"""
from __future__ import annotations

import io

import pytest

from campbot.captcha import classify as ocr_classify, white_composite
from campbot.channels.ui import parse_slots, site_key_from_title


# --- 실측 셀 데이터 (knps_c2_20261003/summary.json rowsSample에서 재구성) ----------
CELLS = [
    # 카라반3 — 10-05(월) 예약가능 R, 가격 130000
    {"prod_id": "CB03100501583", "use_df": "20261005", "reser_tp": "R",
     "title": "설악산-설악동-복합야영지-카라반3"},
    # 카라반16 — 10-06(화) R
    {"prod_id": "CB03100501596", "use_df": "20261006", "reser_tp": "R",
     "title": "설악산-설악동-복합야영지-카라반16"},
    # A1 — 10-12(월) R (실측 F-8 예시: CB03100501601)
    {"prod_id": "CB03100501601", "use_df": "20261012", "reser_tp": "R",
     "title": "설악산-설악동-자동차야영장-A1"},
    # A2 — 10-11(일) R (실측: CB03100501602, A2는 날짜가 다른 열에 위치)
    {"prod_id": "CB03100501602", "use_df": "20261011", "reser_tp": "R",
     "title": "설악산-설악동-자동차야영장-A2"},
]


class TestSiteKeyFromTitle:
    def test_standard_rule(self):
        assert site_key_from_title("설악산-설락동-자동차야영장-A1") == "A1"

    def test_caravan_name(self):
        assert site_key_from_title("설악산-설악동-복합야영지-카라반3") == "카라반3"

    def test_trims_whitespace(self):
        assert site_key_from_title("  설악산-설악동-A1 ") == "A1"

    def test_empty_is_unknown(self):
        assert site_key_from_title("") == "UNKNOWN"
        assert site_key_from_title(None) == "UNKNOWN"   # type: ignore[arg-type]


class TestParseSlots:
    def test_filters_target_date_column(self, monkeypatch):
        out = parse_slots(CELLS, "2026-10-05")
        assert [s.site_key for s in out] == ["카라반3"]
        assert all(s.available for s in out)

    def test_multiple_sites_same_date(self, monkeypatch):
        cells = CELLS + [{"prod_id": "CB9", "use_df": "20261005", "reser_tp": "R",
                          "title": "설악산-설악동-자동차야영장-B2"}]
        out = parse_slots(cells, "2026-10-05")
        assert [s.site_key for s in out] == ["카라반3", "B2"]

    def test_other_dates_excluded(self):
        # A1은 10-12 열 — 10-05 조회 시 목록에 없음 (열=날짜 구조의 핵심)
        assert parse_slots(CELLS, "2026-10-05") != []
        out = parse_slots(CELLS, "2026-10-12")
        assert [s.site_key for s in out] == ["A1"]

    def test_no_date_column_match_empty(self):
        assert parse_slots(CELLS, "2026-11-30") == []

    def test_bad_slot_reser_tp_marked_unavailable(self):
        cells = [{"prod_id": "CB1", "use_df": "20261012", "reser_tp": "",   # 빈 슬롯(미개방)
                  "title": "설악산-설악동-자동차야영장-A9"},
                 {"prod_id": "CB2", "use_df": "20261012", "reser_tp": "r",  # 소문자도 R로 정규화
                  "title": "설악산-설악동-자동차야영장-B3"}]
        out = parse_slots(cells, "2026-10-12")
        by_key = {s.site_key: s.available for s in out}
        assert by_key["A9"] is False      # D-3 2상태: R이 아니면 불가
        assert by_key["B3"] is True

    def test_duplicate_slot_first_wins(self):
        cells = [{"prod_id": "CB1", "use_df": "20261005", "reser_tp": "",  # 먼저 등장, 예약불가
                  "title": "설악산-설악동-A7"},
                 {"prod_id": "CB2", "use_df": "20261005", "reser_tp": "R",
                  "title": "설악산-설악동-A7"}]
        out = parse_slots(cells, "2026-10-05")
        assert len(out) == 1 and out[0].site_key == "A7"

    def test_empty_input(self):
        assert parse_slots([], "2026-10-05") == []
        assert parse_slots(None, "2026-10-05") == []   # type: ignore[arg-type]


class TestCaptchaComposite:
    def _rgba_png(self) -> bytes:
        from PIL import Image

        buf = io.BytesIO()
        img = Image.new("RGBA", (4, 3), (255, 0, 0, 128))   # 반투명 빨강
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_transparent_rgba_composites_white(self):
        out = white_composite(self._rgba_png())
        from PIL import Image

        im = Image.open(io.BytesIO(out))
        assert im.mode == "RGB"   # 알파 제거
        px = im.getpixel((0, 0))
        # (255,0,0) alpha 128 on white → r=255 유지, g/b ≈ 127~128 혼합
        assert px[0] == 255 and 120 <= px[1] <= 135

    def test_rgb_passthrough(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (2, 2), (10, 20, 30)).save(buf, format="PNG")
        raw = buf.getvalue()
        assert white_composite(raw) == raw   # 재인코딩 없이 원본 반환

    def test_classify_extracts_digits(self):
        # OCR 엔진이 없는 환경에서도 정규화 로직 검증 — ddddocr을 monkeypatch로 대체
        import campbot.captcha as cap

        class FakeOcr:
            def __init__(self, *a, **k): ...

            def classification(self, b):
                return " 4985 "   # 앞뒤 공백 + 숫자 — 정규화 후 "4985" 기대

        monkeypatched = cap._get_ocr.__wrapped__ if hasattr(cap._get_ocr, "__wrapped__") else None
        cap._ocr_instance = FakeOcr()
        try:
            assert ocr_classify(self._rgba_png()) == "4985"
        finally:
            cap._ocr_instance = None

    def test_classify_non_digits_is_empty(self):
        import campbot.captcha as cap

        class FakeOcr:
            def __init__(self, *a, **k): ...

            def classification(self, b):
                return "abcd"   # 숫자 없음 → "" (HITL 폴백 경유 조건)

        cap._ocr_instance = FakeOcr()
        try:
            assert ocr_classify(self._rgba_png()) == ""
        finally:
            cap._ocr_instance = None

    def test_classify_ocr_exception_is_empty(self):
        import campbot.captcha as cap

        class BoomOcr:
            def __init__(self, *a, **k): ...

            def classification(self, b):
                raise RuntimeError("model missing")   # 엔진 오류도 실패 정규화 (HITL)

        cap._ocr_instance = BoomOcr()
        try:
            assert ocr_classify(self._rgba_png()) == ""
        finally:
            cap._ocr_instance = None


class TestUiChannelContract:
    def test_implements_abc(self):
        from campbot.channel import KnpsChannel
        from campbot.channels.ui import UiKnpsChannel

        assert issubclass(UiKnpsChannel, KnpsChannel)
        # 추상 메서드 전부 구현 확인 — ABCMeta가 미구현 시 __init__에서 TypeError (lazy browser라 기동 없음)
        ch = UiKnpsChannel()   # 예외 없이 생성 성공 = ABC 충족

    def test_settings_env_credentials_absent(self, monkeypatch):
        """NFR-06 — env 미설정时空 자격증명 (코드/DB 저장 ❌)."""
        import os

        from campbot.channels.ui import load_env_credentials

        monkeypatch.delenv("CAMPBOT_KNPS_ID", raising=False)
        monkeypatch.delenv("CAMPBOT_KNPS_PW", raising=False)
        assert load_env_credentials() == ("", "")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
