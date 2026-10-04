"""C-1 CAPTCHA OCR — KNPS 자동예약 방지숫자 (PRD-07 v1.3 §4 실측 지문).

실측 사실:
  - 이미지 = `GET /reserCaptcha.do` → PNG 100×50 RGBA, **배경 투명(alPHA=0)**
  - 피트폴: 투명배경 이미지를 그대로 인식하면 빈 문자열 → **흰색 배경 합성 후 인식 필수**
정책 (Q-1b): OCR 2회(중간 리프레시 1회) 실패 = HumanInputRequired(HITL 폴백, 자동 재시도 ❌).

ddddocr은 최초 사용 시에만 로딩 — 채널 모듈 import 비용과 격리.
"""
from __future__ import annotations

import io
import re

_DIGITS = re.compile(r"\d{3,5}")
_ocr_instance: object | None = None


def _get_ocr() -> object:
    """ddddocr 단일 인스턴스 캐시 (모델 로딩이 한 번만)."""
    global _ocr_instance
    if _ocr_instance is None:
        import ddddocr  # lazy — 무거운 모델 로딩을 import 시점이 아닌 최초 사용으로

        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
    return _ocr_instance


def white_composite(png_bytes: bytes) -> bytes:
    """투명배경 RGBA → 흰색 배경에 합성해 RGB PNG 바이트 반환 (실측 피트폴 대응).

    이미 RGB인 입력은 그대로(재인코딩 없이) 돌려준다.
    """
    from PIL import Image  # 함수 내 import — Pillow는 venv 필수 의존(PRD-07 C-1)

    img = Image.open(io.BytesIO(png_bytes))
    if img.mode != "RGBA":
        return png_bytes if img.mode == "RGB" else _reencode_rgb(img, format_hint=img.format)
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    buf = io.BytesIO()
    bg.save(buf, format="PNG")
    return buf.getvalue()


def _reencode_rgb(img, format_hint: str | None) -> bytes:
    from PIL import Image  # noqa: F811

    rgb = img.convert("RGB") if img.mode != "RGB" else img
    fmt = format_hint or "PNG"
    buf = io.BytesIO()
    rgb.save(buf, format=fmt if fmt in ("PNG", "JPEG") else "PNG")
    return buf.getvalue()


def classify(png_bytes: bytes) -> str:
    """CAPTCHA 숫자 인식. 성공 시 3~5자리 숫자 문자열, 실패/비숫자는 빈 문자열."""
    try:
        raw = _get_ocr().classification(white_composite(png_bytes)) or ""  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 — 인식 엔진 오류도 "실패"로 정규화 (HITL 폴백 경유)
        return ""
    m = _DIGITS.search(raw)
    return m.group(0) if m else ""


def reset() -> None:
    """테스트 훅 — 캐시된 OCR 인스턴스 해제."""
    global _ocr_instance
    _ocr_instance = None
