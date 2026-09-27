"""로그 설정 + PII 마스킹 (NFR-05/NFR-07 강제장치).

원칙: 로그·알림 어디에도 주민번호 원문/연락처 전체 노출 금지.
"""
from __future__ import annotations

import logging
import re
import sys

# --- 패턴 정의 -----------------------------------------------------------
RRN_RE = re.compile(r"\b\d{6}[ -]?\d{7}\b")                 # 주민번호 13자리(대시可有)
# 국내 번호: 0 + 통신사/지역코드 1~3자리(예: 010·011·02) + 구분자 + 중간부 3~4자리 + 구분자 + 끝자리 4
# 예: 010-9876-5432 / 011-123-4567 / 02-1234-5678 (구분자 없는 "01098765432"도 매칭)
PHONE_RE = re.compile(r"(?<!\d)0[0-9]{1,3}[ .-]?\d{3,4}[ .-]?\d{4}(?!\d)")


def mask_rrn(text: str) -> str:
    return RRN_RE.sub("[RRN]", text)


def mask_phone(text: str) -> str:
    def _sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "*" * max(len(digits) - 4, 1) + digits[-4:]

    return PHONE_RE.sub(_sub, text)


def mask_pii(text: str) -> str:
    """로그/알림용 PII 마스킹. 순서: RRN → PHONE."""
    return mask_phone(mask_rrn(text))


# --- 로거 구성 -----------------------------------------------------------
class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            msg = record.getMessage()
            if hasattr(record, "exc_info") and record.exc_info[1]:
                import traceback

                msg += "\n" + "".join(
                    traceback.format_exception(*record.exc_info)  # type: ignore[misc]
                )
            return super().format(record.__class__(record.name, record.levelno, record.pathname,
                                                     record.lineno, mask_pii(msg), None,
                                                     record.exc_info, record.stack_info))
        except Exception:  # pragma: no cover - 마스킹 실패해도 로그는 살려야 함
            return super().format(record)


def get_logger(name: str = "campbot", level: int | None = None) -> logging.Logger:
    logger = logging.getLogger("campbot")
    if not logger.handlers and (level is not None or __debug__):
        _configure()
    lg = logger.getChild(name) if name != "campbot" else logger
    return lg


def _configure(level: int | None = None) -> None:
    root = logging.getLogger("campbot")
    if getattr(root, "_campbot_configured", False):
        return
    fmt = _RedactingFormatter("%(asctime)s %(levelname)-5s %(name)s | %(message)s")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    if level is not None:
        root.setLevel(level)
    else:
        root.setLevel(logging.INFO)
    root._campbot_configured = True  # type: ignore[attr-defined]
