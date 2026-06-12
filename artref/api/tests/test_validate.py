"""가드레일(safety/validate.py) 회귀 테스트 — 닫힌 세계·금지표현·신뢰도 캡·폴백.

이 앱의 핵심 안전 가치(환각·평가어 차단)가 사는 모듈인데 직접 테스트가 없었다. 여기서 고정한다.
실행: artref/api 에서  python -m tests.test_validate
"""
import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from safety.validate import (validate_guide, template_fallback, coach_with_guardrails,
                             Grounding, Policy)
from pipeline.diagnose import taxonomy

TAX = taxonomy()
TAX_IDS = set(TAX)


def _dx(degraded=False):
    return {"primary_focus": "weight_balance", "degraded": degraded,
            "observations": [{"sub_problem": "weight_balance", "confidence": 0.6},
                             {"sub_problem": "value_structure", "confidence": 0.4}]}


def _guide(blocks, primary="weight_balance", synthesis="", one_thing="", degraded=False):
    return json.dumps({"mode": "coach", "primary_focus": primary, "degraded": degraded,
                       "blocks": blocks, "synthesis": synthesis, "one_thing": one_thing},
                      ensure_ascii=False)


def _blk(sp="weight_balance", obs="무게중심이 한쪽으로", eff="기우뚱해 보임",
         dirn="반대로 그려보기", refs=None, conf=0.5):
    return {"sub_problem": sp, "observation": obs, "effect": eff, "direction": dirn,
            "reference_ids": refs or [], "confidence": conf}


def t_valid_coach_passes():
    g = validate_guide(_guide([_blk(refs=["r1"])]), _dx(), {"r1", "r2"}, TAX_IDS)
    assert g.mode == "coach" and g.blocks[0].sub_problem == "weight_balance"


def t_non_coach_returns_asis():
    raw = json.dumps({"mode": "clarify", "message": "무엇을 봐줄까요?"})
    g = validate_guide(raw, _dx(), set(), TAX_IDS)
    assert g.mode == "clarify"


def t_primary_focus_not_in_taxonomy():
    raw = _guide([_blk()], primary="not_a_real_axis")
    try:
        validate_guide(raw, _dx(), set(), TAX_IDS)
        assert False, "taxonomy 밖 primary_focus 인데 통과"
    except Grounding:
        pass


def t_unknown_subproblem_block():
    raw = _guide([_blk(sp="color_harmony")])   # 진단 obs 에 없음
    try:
        validate_guide(raw, _dx(), set(), TAX_IDS)
        assert False, "진단에 없는 sub_problem 인데 통과"
    except Grounding:
        pass


def t_invented_refs_rejected():
    raw = _guide([_blk(refs=["ghost"])])
    try:
        validate_guide(raw, _dx(), {"r1"}, TAX_IDS)   # ghost 는 retrieved 밖
        assert False, "지어낸 ref 인데 통과"
    except Grounding:
        pass


def t_forbidden_phrasing_policy():
    raw = _guide([_blk(obs="초보치고 잘 그렸어요")])   # '초보'·'잘 그렸' = 금지
    try:
        validate_guide(raw, _dx(), set(), TAX_IDS)
        assert False, "금지표현인데 통과"
    except Policy:
        pass


def t_confidence_capped_to_obs():
    g = validate_guide(_guide([_blk(conf=0.95)]), _dx(), set(), TAX_IDS)  # obs=0.6
    assert g.blocks[0].confidence <= 0.6 + 1e-9, g.blocks[0].confidence


def t_degraded_caps_confidence():
    g = validate_guide(_guide([_blk(conf=0.6)], degraded=True), _dx(degraded=True), set(), TAX_IDS)
    assert g.blocks[0].confidence <= 0.4 + 1e-9, g.blocks[0].confidence


def t_template_fallback_uses_taxonomy():
    refs_by_sp = {"weight_balance": [("r1", ""), ("r2", "")]}
    g = template_fallback(_dx(), refs_by_sp, TAX)
    assert g.mode == "coach"
    wb = TAX["weight_balance"]
    assert g.blocks[0].observation == wb["what_to_observe"]
    assert g.blocks[0].reference_ids == ["r1", "r2"]


class _BadLLM:
    def complete_json(self, prompt):
        return json.dumps({"mode": "coach", "primary_focus": "weight_balance",
                           "degraded": False,
                           "blocks": [_blk(sp="color_harmony")]})  # 항상 grounding 위반


class _GoodLLM:
    def complete_json(self, prompt):
        return _guide([_blk(refs=["r1"])])


def t_guardrails_fallback_after_retries():
    refs_by_sp = {"weight_balance": [("r1", "")]}
    g = coach_with_guardrails("p", _dx(), refs_by_sp, {"r1"}, TAX, _BadLLM(), max_retries=2)
    # 반복 위반 → 템플릿 폴백(근거 있는 결정적 블록)
    assert g.mode == "coach"
    assert g.blocks[0].sub_problem == "weight_balance"
    assert g.blocks[0].observation == TAX["weight_balance"]["what_to_observe"]


def t_guardrails_accepts_good_and_sets_refs():
    refs_by_sp = {"weight_balance": [("r1", ""), ("r9", "")]}
    g = coach_with_guardrails("p", _dx(), refs_by_sp, {"r1", "r9"}, TAX, _GoodLLM())
    assert g.mode == "coach"
    assert g.blocks[0].reference_ids == ["r1", "r9"]   # _set_refs 가 검색 결과로 채움


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 닫힌세계·금지표현·신뢰도캡·degraded·폴백·refs")


if __name__ == "__main__":
    run()
