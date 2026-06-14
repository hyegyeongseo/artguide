"""diagnose 자동측정 3종(색/빛/손) 테스트 — 신호 추출 가드 + 스코어러 임계 검증.

확인:
  1) 단색/빈 이미지(분산≈0)는 색/빛 신호를 안 낸다(블랭크 오발화 방지 — 기존 eval 불변의 근거).
  2) 채도 높고 색상 넓게 퍼진 이미지 → color_signals 산출 → s_color_harmony 발화.
  3) 방향성 광원(그라데이션)은 '평면적' 으로 안 잡힌다(ramp 큼). 평탄/랜덤만 발화.
  4) s_hand_structure 는 HAND_AUTO 신호(_hand)가 있을 때만 발화(기본 OFF → None).
실행: artref/api 에서  python -m tests.test_diagnose_scorers
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from PIL import Image
from pipeline import diagnose as D


def _grad(n=64):
    w = np.tile(np.linspace(0, 1, n), (n, 1))
    return Image.fromarray((w * 255).astype("uint8")).convert("RGB")


def t_blank_guard():
    flat = Image.new("RGB", (48, 48), (20, 20, 20))
    assert D.color_signals(flat) == {}, "단색은 색 신호 없음"
    assert D.light_signals(flat, {"status": "skipped"}) == {}, "단색은 빛 신호 없음"


def t_color_signal_and_scorer():
    hsv = np.zeros((48, 48, 3), "uint8")
    hsv[..., 0] = np.tile(np.linspace(0, 255, 48), (48, 1)).astype("uint8")  # 넓은 hue
    hsv[..., 1] = 220                                                        # 높은 채도
    hsv[..., 2] = 200
    img = Image.fromarray(hsv, "HSV").convert("RGB")
    sig = D.color_signals(img)
    assert sig.get("sat_mean", 0) > 0.6 and sig.get("hue_spread", 0) > 0.55, sig
    assert D.s_color_harmony(sig) is not None, "넓은 채도/색상 → 발화"
    assert D.s_color_harmony({"sat_mean": 0.3, "hue_spread": 0.2}) is None


def t_color_scorer_quiet_on_muted():
    assert D.s_color_harmony({"sat_mean": 0.5, "hue_spread": 0.4}) is None


def t_light_direction_scorer():
    # 스코어러 자체: 평탄(거의 0 ramp) → 발화 / 방향성(ramp 큼) → 비발화
    assert D.s_light_direction({"light_ramp": 0.005}) is not None
    assert D.s_light_direction({"light_ramp": 0.05}) is None
    # 형체 미검출(pose 'ok' 아님): 배경 ramp 오판 방지 위해 광원 방향 미측정 → 빈 dict, scorer 침묵
    assert D.light_signals(_grad(), {"status": "skipped"}) == {}
    assert D.s_light_direction({}) is None
    # 형체가 있으면(전신 bbox) 방향성 그라데이션의 ramp 가 커서 '평면적' 으로 안 잡힌다
    kp = [(0.2, 0.1, 1.0), (0.8, 0.1, 1.0), (0.2, 0.9, 1.0),
          (0.8, 0.9, 1.0), (0.5, 0.5, 1.0), (0.5, 0.3, 1.0), (0.5, 0.7, 1.0)]
    sig = D.light_signals(_grad(), {"status": "ok", "keypoints": kp})
    assert sig["light_ramp"] > 0.015, ("방향성 광원은 '평면적' 으로 안 잡혀야", sig)
    assert D.s_light_direction(sig) is None


def t_hand_scorer_gated():
    assert D.s_hand_structure({}) is None, "신호 없으면 None(HAND_AUTO 기본 OFF)"
    assert D.s_hand_structure({"_hand": (0.4, "손바닥 평면이 정면")}) == (0.4, "손바닥 평면이 정면")


def t_hand_signals_off_by_default():
    os.environ.pop("HAND_AUTO", None)
    assert D.hand_signals(_grad()) == {}, "HAND_AUTO 미설정이면 빈 dict"


def t_scorers_registered():
    for sid in ("color_harmony", "light_direction", "hand_structure"):
        assert sid in D.SCORERS, f"{sid} 스코어러 미등록"


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 블랭크가드·색발화·빛방향·손게이트·등록")


if __name__ == "__main__":
    run()
