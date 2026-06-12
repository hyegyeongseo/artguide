"""screen 모더레이션 테스트 — CLIP 임베더를 주입(가짜)해 결정적으로 검증.

확인:
  1) 명백한 unsafe(unsafe 앵커에 가깝고 safe 앵커와 차이 큼) → block.
  2) 예술적 인물·해부 습작(safe 앵커가 받쳐줌, margin 미달) → allow (도메인 오차단 방지 핵심).
  3) 경계(margin 미달) → allow.
  4) embedder 실패 + fail_open=True → allow / fail_open=False → block.
  5) provider 가 block 하면 baseline 안 보고 block.
실행: artref/api 에서  python -m tests.test_screen
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from safety import screen as S


class FakeEmbedder:
    """text(앵커)=one-hot, image()=각 앵커 dim 에 코사인을 채운 벡터 → _cos 가 그 값을 그대로 냄."""
    def __init__(self, image_cos):
        self.labels = list(image_cos.keys())
        self.idx = {lab: i for i, lab in enumerate(self.labels)}
        self.N = max(8, len(self.labels))
        self._img = np.zeros(self.N, dtype="float32")
        for lab, c in image_cos.items():
            self._img[self.idx[lab]] = float(c)
        self.model_id = "fake"

    def image(self, pil):
        return self._img.copy()

    def text(self, s):
        v = np.zeros(self.N, dtype="float32")
        if s in self.idx:
            v[self.idx[s]] = 1.0
        return v


class BrokenEmbedder:
    def image(self, pil):
        raise RuntimeError("no clip")

    def text(self, s):
        raise RuntimeError("no clip")


PIL = object()
U0 = S.UNSAFE_ANCHORS[0]
SAFE_FIG = S.SAFE_ANCHORS[0]   # "artistic figure drawing or anatomical study"


def t_block_obvious_unsafe():
    emb = FakeEmbedder({U0: 0.33, SAFE_FIG: 0.10})
    v = S.screen(PIL, embedder=emb)
    assert not v["allow"], v
    assert "unsafe" in (v["reason"] or ""), v


def t_allow_figure_study():
    # 인물 습작: unsafe 앵커와도 어느 정도 가깝지만 safe(figure) 앵커가 더/비슷하게 받쳐줌 → margin 미달 → allow
    emb = FakeEmbedder({U0: 0.30, SAFE_FIG: 0.29})
    v = S.screen(PIL, embedder=emb)
    assert v["allow"], v


def t_allow_below_min_abs():
    # unsafe 가 safe 보다 약간 높지만 절대값이 MIN_ABS 미만 → 막지 않음(보수적)
    emb = FakeEmbedder({U0: 0.15, SAFE_FIG: 0.05})
    v = S.screen(PIL, embedder=emb)
    assert v["allow"], v


def t_fail_open_vs_closed():
    op = S.screen(PIL, embedder=BrokenEmbedder(), fail_open=True)
    assert op["allow"] and op["scores"].get("skipped"), op
    cl = S.screen(PIL, embedder=BrokenEmbedder(), fail_open=False)
    assert not cl["allow"], cl


def t_provider_blocks():
    def prov(pil):
        return {"allow": False, "reason": "provider blocked"}
    v = S.screen(PIL, provider=prov, embedder=FakeEmbedder({U0: 0.0, SAFE_FIG: 0.9}))
    assert not v["allow"] and "provider" in v["reason"], v


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — unsafe차단·인물습작허용·경계허용·fail모드·provider우선")


if __name__ == "__main__":
    run()
