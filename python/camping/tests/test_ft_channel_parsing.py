"""[유닛] UiForestTripChannel 순수 파싱·CLI 채널 선택 — 숲나들e 접속 ❌ / Playwright ❌ (NFR-10).

검증 대상:
  - date_to_compact : YYYY-MM-DD → YYYYMMDD (실측 필드 형식) + 잘못된 형식 거부
  - parse_facility_list : selectInsttListForSearch.do 응답(JSON dict/list) → [{id,name}], name_hint 필터
      근거: output/ft_js_analysis_20261010/analysis.json ajax_bodies (실측 본문 캡처)
  - parse_search_result : 결과 페이지 "예약 가능한 잔여 객실이 없습니다" 판정 + 상품행/미확보 분류 (허위 양성 차단)
      근거: output/ft_result_v2_20261010/search_result.json (본문 실측)
  - CLI --channel / CAMPBOT_CHANNEL env → UiForestTripChannel 팩토리 (AD-6 교체성)
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from campbot.channels.ft import (  # noqa: E402
    NO_SLOT_MARKER,
    date_to_compact,
    parse_facility_list,
    parse_search_result,
)


# --- 실측 데이터 (ft_js_analysis_20261010 ajax_bodies / ft_result_v2 본문에서 재구성) ----

FCLIST_RESPONSE = {
    "insttList": [
        {"insttId": "ID02030060", "insttNm": "(강진군)주작산자연휴양림"},
        {"insttId": "0181", "insttNm": "(장성군)방장산자연휴양림"},
        {"insttId": "ID04030010", "insttNm": "(화순군)무등산편백자연휴양림"},
    ]
}

BODY_NO_SLOT = (
    "통합예약 일반예약  예약 가능한 잔여 객실이 없습니다.   자세한 잔여객실 현황을 확인하시려면"
    " 월별현황조회 메뉴를 이용해주세요."
)


class TestDateToCompact:
    def test_valid(self):
        assert date_to_compact("2026-10-14") == "20261014"

    @pytest.mark.parametrize("bad", ["2026/10/14", "2026-10", "", "abcdefg1", None])
    def test_invalid_rejected(self, bad):
        with pytest.raises(ValueError):
            date_to_compact(bad)  # type: ignore[arg-type]


class TestParseFacilityList:
    def test_full_list_order_kept(self):
        out = parse_facility_list(FCLIST_RESPONSE)
        assert [x["id"] for x in out] == ["ID02030060", "0181", "ID04030010"]
        assert all(x["name"] for x in out)

    def test_name_hint_filters(self):
        out = parse_facility_list(FCLIST_RESPONSE, name_hint="방장산")
        assert out == [{"id": "0181", "name": "(장성군)방장산자연휴양림"}]

    def test_no_match_empty(self):
        assert parse_facility_list(FCLIST_RESPONSE, name_hint="설악산") == []

    def test_list_payload_and_missing_keys_tolerated(self):
        out = parse_facility_list([
            {"insttId": "0201", "insttNm": "(진도군)진도자연휴양림"},
            {"insttId": "", "insttNm": ""},       # 빈 항목 제외
            None,                                  # 비dict 무시
        ])
        assert out == [{"id": "0201", "name": "(진도군)진도자연휴양림"}]

    def test_empty_payload(self):
        assert parse_facility_list({}) == []
        assert parse_facility_list(None) == []


class TestParseSearchResult:
    def test_no_slot_marker(self):
        out = parse_search_result(BODY_NO_SLOT, [{"h": "/rep/or/fcfsRsrvtMain.do?goodsId=123", "t": "객실"}])
        assert out["no_slot"] is True
        # 문구 감지 시 상품행 무시 확정 (허위 양성 차단)
        assert out["unknown_goods_structure"] is False

    def test_no_slot_marker_constant_matches(self):
        assert NO_SLOT_MARKER in BODY_NO_SLOT

    def test_empty_body_unknown(self):
        out = parse_search_result("", links=[])
        assert out["no_slot"] is False
        assert out["goods"] == []
        assert out["unknown_goods_structure"] is True   # 빈 예약으로 오해 ❌ — 사람 판단 경유 신호

    def test_goods_links_filtered(self):
        links = [
            {"h": "javascript:movePageUsingNetFunnel('/rep/or/fcfsRsrvtMain.do?hmpgId=FRIP', 'action1')"},
            {"h": "/rep/or/fcfsRsrvtMain.do?goodsId=G018120261014&date=20261014", "t": "(장성군)방장산-객실A"},
            {"h": "/portal/other.html"},
        ]
        out = parse_search_result("상품이 있습니다", links=links)
        assert out["no_slot"] is False
        # javascript: 이동 + 식별자 없는 링크 제외, goodsId 링크만 채택
        assert len(out["goods"]) == 1 and "G018120261014" in out["goods"][0]["href"]


class TestCliChannelSelection:
    def _args(self, channel):
        class A:  # noqa: D401 — argparse.Namespace 대용 (필드: channel)
            pass

        a = A()
        a.channel = channel
        return a

    def test_default_is_knps(self):
        from campbot.channel import KnpsChannel
        from campbot.cli import _channel_factory_for
        from campbot.channels import UiKnpsChannel

        ch = _channel_factory_for(self._args(None))()
        assert isinstance(ch, UiKnpsChannel) and isinstance(ch, KnpsChannel)

    def test_flag_foresttrip(self):
        from campbot.cli import _channel_factory_for
        from campbot.channel import KnpsChannel
        from campbot.channels import UiForestTripChannel

        ch = _channel_factory_for(self._args("foresttrip"))()
        assert isinstance(ch, UiForestTripChannel) and isinstance(ch, KnpsChannel)

    def test_env_var_ft_alias(self):
        from campbot.channel import KnpsChannel
        from campbot.cli import _channel_factory_for
        from campbot.channels import UiKnpsChannel, UiForestTripChannel

        monkeypatch = pytest.MonkeyPatch()
        with monkeypatch.context() as m:
            m.delenv("CAMPBOT_CHANNEL", raising=False)
            assert isinstance(_channel_factory_for(self._args(None))(), UiKnpsChannel)
            m.setenv("CAMPBOT_CHANNEL", "ft")
            ch = _channel_factory_for(self._args(None))()
            assert isinstance(ch, UiForestTripChannel) and isinstance(ch, KnpsChannel)
