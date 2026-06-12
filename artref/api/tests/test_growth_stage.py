"""growth_stage(내부 성장 단계·콜드스타트) 회귀 테스트.

핵심 불변식: stage 는 '판정'이 아니라 커리큘럼 좌표이며, 콜드스타트 진입점은 그림에서 측정된
약점을 커리큘럼(구조 먼저) 순서로 고른다. 이력이 쌓이면 apply_cold_start 는 손대지 않는다.
실행: artref/api 에서  python -m tests.test_growth_stage
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.growth_stage import (estimate_stage, cold_start_focus, is_cold,
                                    apply_cold_start, FOUNDATION, DEVELOPING, REFINING)

CURR = ["proportion", "weight_balance", "action_line", "joint_articulation",
        "foreshortening", "hand_structure", "value_structure"]


def t_estimate_stage_foundation_when_nothing_steady():
    stage, ratio = estimate_stage(steady=0, total=7)
    assert stage == FOUNDATION and ratio == 0.0


def t_estimate_stage_refining_when_half_steady():
    stage, _ = estimate_stage(steady=4, total=7)
    assert stage == REFINING


def t_estimate_stage_developing_middle():
    stage, _ = estimate_stage(steady=2, total=7)
    assert stage == DEVELOPING


def t_estimate_stage_tries_bump_to_developing():
    # 아직 자리잡은 축이 없어도 시도가 쌓이면 foundation 을 벗어난다(노력 반영).
    stage, _ = estimate_stage(steady=0, total=7, total_tries=2)
    assert stage == DEVELOPING


def t_estimate_stage_handles_zero_total():
    stage, ratio = estimate_stage(steady=0, total=0)
    assert stage == FOUNDATION and 0.0 <= ratio <= 1.0


def t_cold_start_picks_earliest_in_curriculum():
    # action_line(앞) 과 value_structure(뒤) 둘 다 떴으면 앞쪽을 진입점으로.
    assert cold_start_focus(["value_structure", "action_line"], CURR) == "action_line"


def t_cold_start_none_when_no_flag():
    assert cold_start_focus([], CURR) is None


def t_is_cold_true_on_empty_and_flag():
    assert is_cold(None) is True
    assert is_cold({"cold": True}) is True
    assert is_cold({"cold": False, "steady": [], "recurring": []}) is False


def t_apply_cold_start_overrides_focus_when_cold():
    g = {"cold": True, "current_focus": "proportion", "next_goal": "weight_balance"}
    out = apply_cold_start(g, ["joint_articulation"], CURR)
    assert out["current_focus"] == "joint_articulation"
    # 다음 목표도 커리큘럼상 그 다음으로 갱신.
    assert out["next_goal"] == "foreshortening"


def t_apply_cold_start_noop_when_not_cold():
    g = {"cold": False, "current_focus": "proportion", "next_goal": "weight_balance"}
    out = apply_cold_start(g, ["hand_structure"], CURR)
    assert out["current_focus"] == "proportion"   # 이력 있으면 로드맵 우선(안 건드림)


def t_apply_cold_start_noop_when_no_measured():
    g = {"cold": True, "current_focus": "proportion", "next_goal": "weight_balance"}
    out = apply_cold_start(g, [], CURR)
    assert out["current_focus"] == "proportion"   # 측정 약점 없으면 커리큘럼 기본 유지


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 내부단계·콜드스타트 진입점·비노출 불변식")


if __name__ == "__main__":
    run()
