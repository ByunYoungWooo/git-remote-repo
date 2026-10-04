"""channels — KnpsChannel 구현체 패키지 (AD-6: 인터페이스 뒤로 교체 가능)."""
from .ui import UiKnpsChannel  # noqa: F401

__all__ = ["UiKnpsChannel"]
