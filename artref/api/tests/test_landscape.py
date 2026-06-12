"""풍경(landscape) track 테스트 — taxonomy 확장 + 프로파일 게이팅 + persona surface + lexicon.
실행: artref/api 에서  python -m tests.test_landscape
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from PIL import Image
from pipeline.diagnose import diagnose, taxonomy
from pipeline.profiles import PROFILES, resolve_profile, POSE_DEPENDENT
from pipeline import router as R

LAND = set(PROFILES["landscape"]["subproblems"])
SCENE = {"analyzable": True, "subject": {"person": {"present": False}}}
NO_POSE = {"status": "skipped", "reason": "no_person_detected"}


def _landscape_img():
    """가운데 수평 전이(지평선 0.5) + 상·하 비슷한 질감(falloff 작음) → 두 측정 축 발화."""
    rs = np.random.RandomState(3)
    g = np.empty((90, 90))
    g[:45] = 0.4 + rs.rand(45, 90) * 0.15
    g[45:] = 0.65 + rs.rand(45, 90) * 0.15
    return Image.fromarray((g * 255).astype("uint8")).convert("RGB")


def t_taxonomy_has_landscape_axes():
    tax = taxonomy()
    for a in ("linear_perspective", "atmospheric_perspective", "depth_layering", "horizon_placement"):
        assert a in tax, a
        assert tax[a]["reference_query"] and tax[a]["what_to_observe"]


def t_landscape_profile_order():
    assert "atmospheric_perspective" in LAND and "horizon_placement" in LAND
    assert "weight_balance" not in LAND          # 포즈 축은 풍경에 없음


def t_gating_no_pose_leak():
    dx = diagnose(SCENE, NO_POSE, _landscape_img(),
                  personas=["composition", "light", "color"], user_terms=set(),
                  profile=PROFILES["landscape"])
    sps = [o["sub_problem"] for o in dx["observations"]]
    assert sps, "관찰이 비면 안 됨"
    for sp in sps:
        assert sp in LAND, f"풍경 track에 비풍경 축 누출: {sp}"
    # 포즈 의존 축은 절대 안 나와야
    assert not (set(sps) & POSE_DEPENDENT), sps


def t_measured_landscape_axes_surface():
    dx = diagnose(SCENE, NO_POSE, _landscape_img(),
                  personas=["composition", "light", "color"], user_terms=set(),
                  profile=PROFILES["landscape"])
    sps = {o["sub_problem"] for o in dx["observations"]}
    # 측정 축(대기원근/지평선) 중 최소 하나는 측정으로 떠야(이 합성 이미지가 둘 다 유발)
    measured = {o["sub_problem"] for o in dx["observations"] if o["measured"]}
    assert measured & {"atmospheric_perspective", "horizon_placement"}, dx["observations"]


def t_persona_only_axes_via_user_terms():
    # 선원근/깊이는 auto=false라 user_terms(칩)로 콕 집으면 최우선 관찰로 surface
    dx = diagnose(SCENE, NO_POSE, _landscape_img(),
                  personas=["composition", "light", "color"],
                  user_terms={"linear_perspective"}, profile=PROFILES["landscape"])
    assert dx["observations"][0]["sub_problem"] == "linear_perspective", dx["observations"]


def t_figure_track_excludes_landscape():
    # 인물 트랙에선 풍경 축이 절대 안 나옴(measured 신호가 떠도 게이팅으로 제외)
    fig = resolve_profile("realistic_figure")
    dx = diagnose({"analyzable": True, "subject": {"person": {"present": True}}},
                  NO_POSE, _landscape_img(), personas=["pose", "anatomy"],
                  user_terms=set(), profile=fig)
    sps = {o["sub_problem"] for o in dx["observations"]}
    assert not (sps & {"atmospheric_perspective", "horizon_placement",
                       "linear_perspective", "depth_layering"}), sps


def t_lexicon_landscape_keywords():
    assert R.detect_terms("대기원근이 약해요") == {"atmospheric_perspective"}
    assert R.detect_terms("소실점이 안 맞아") == {"linear_perspective"}
    assert R.detect_terms("선원근 좀 봐줘") == {"linear_perspective"}
    assert R.detect_terms("공간감이 없어") == {"depth_layering"}
    assert R.detect_terms("지평선 위치") == {"horizon_placement"}
    # '원근'은 여전히 단축(인물 기본) — 풍경 어휘와 충돌 안 함
    assert R.detect_terms("원근이 이상해") == {"foreshortening"}


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — taxonomy·프로파일·게이팅·측정surface·persona·인물제외·lexicon")


if __name__ == "__main__":
    run()
