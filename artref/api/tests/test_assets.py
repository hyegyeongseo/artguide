"""guide-asset 선택층 스텁 테스트 — DB·LLM·FastAPI 없이 순수 로직만 검증.

확인하는 안전 속성:
  1) 적재 자료 0개여도 슬롯이 svg 도식 바닥으로 채워진다(절대 비지 않음).
  2) 축별 선호 순서대로 적재 type을 고른다(없으면 다음 선호 → 바닥).
  3) AI_AVOID 축(손·해부·비율)은 ai_example을 후보에서 제외한다.
  4) degraded + 포즈축이면 backbone_3d를 후보에서 제외(측정 못 한 전신 포즈 확신 방지).
  5) grounding: 후보 밖 ref_id는 검증에서 버려지고 바닥으로 폴백.
  6) attach: 블록마다 자료가 *정확히 하나*(one-at-a-time).
실행: artref/api 에서  python -m tests.test_assets   (또는 pytest)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import assets as A


def t_floor_when_empty():
    a = A.pick("value_structure", loaded=None)
    assert a["type"] == "svg" and a["ref_id"] == "floor:value_structure", a
    assert A.floor_svg("value_structure").startswith("<svg"), "도식 SVG가 실제로 나와야 함"


def t_axis_pref_backbone_first():
    loaded = [{"type": "ai_example", "ref_id": "ai1"},
              {"type": "svg", "ref_id": "sv1"},
              {"type": "backbone_3d", "ref_id": "bb1"}]
    a = A.pick("foreshortening", loaded=loaded)
    assert a["ref_id"] == "bb1", ("단축은 3D 백본 우선", a)


def t_axis_pref_feel_falls_to_ai():
    # 빛 방향은 AI 우선. 적재에 svg는 없고 ai만 → ai 선택(바닥보다 앞).
    loaded = [{"type": "ai_example", "ref_id": "lite1"}]
    a = A.pick("light_direction", loaded=loaded)
    assert a["ref_id"] == "lite1", ("느낌 축은 AI 예시가 바닥보다 먼저", a)


def t_value_method_first():
    # 명암은 svg(방법) 우선. svg·ai 둘 다 적재 → svg.
    loaded = [{"type": "ai_example", "ref_id": "ai1"}, {"type": "svg", "ref_id": "sv1"}]
    a = A.pick("value_structure", loaded=loaded)
    assert a["ref_id"] == "sv1", ("명암은 방법 도해 우선", a)
    # 적재가 ai뿐이면 ai로(영영 안 뜨는 일 없음)
    a2 = A.pick("value_structure", loaded=[{"type": "ai_example", "ref_id": "ai1"}])
    assert a2["ref_id"] == "ai1", a2


def t_ai_avoided_on_hands():
    loaded = [{"type": "ai_example", "ref_id": "aihand"}, {"type": "svg", "ref_id": "svhand"}]
    a = A.pick("hand_structure", loaded=loaded)
    assert a["type"] != "ai_example", ("손엔 AI 예시 금지", a)
    assert a["ref_id"] == "svhand", a
    # ai만 적재돼 있어도 → 바닥(ai는 후보에서 빠지므로)
    a2 = A.pick("hand_structure", loaded=[{"type": "ai_example", "ref_id": "aihand"}])
    assert a2["ref_id"] == "floor:hand_structure", a2


def t_backbone_dropped_when_degraded():
    loaded = [{"type": "backbone_3d", "ref_id": "bb1"}]
    # 정상: 3D 백본 선택
    assert A.pick("foreshortening", loaded=loaded, degraded=False)["ref_id"] == "bb1"
    # degraded(전신 미검출) + 포즈축: 3D 백본 제외 → 바닥
    a = A.pick("foreshortening", loaded=loaded, degraded=True)
    assert a["ref_id"] == "floor:foreshortening", ("degraded면 전신 3D 확신 금지", a)


def t_grounding_rejects_outsider():
    cands = A.gather_candidates("value_structure", loaded=[{"type": "svg", "ref_id": "sv1"}])
    # LLM/외부가 후보에 없는 id를 골랐다고 가정
    hallucinated = {"type": "svg", "ref_id": "does_not_exist", "label": "도식"}
    assert A.validate(hallucinated, cands) is None, "후보 밖은 버려야 함"
    # 후보 안은 통과
    assert A.validate({"type": "svg", "ref_id": "sv1", "label": "도식"}, cands) is not None


def t_attach_one_per_block():
    blocks = [{"sub_problem": "value_structure"}, {"sub_problem": "composition_balance"}]
    A.attach(blocks, degraded=False, index={"value_structure": [{"type": "svg", "ref_id": "sv1"}]})
    assert blocks[0]["guide_asset"]["ref_id"] == "sv1"
    assert blocks[1]["guide_asset"]["ref_id"] == "floor:composition_balance"
    # 각 블록 자료는 dict 하나(리스트 아님) = one-at-a-time
    assert isinstance(blocks[0]["guide_asset"], dict)


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 슬롯 비지않음·축선호·AI배제·degraded·grounding·one-at-a-time")


if __name__ == "__main__":
    run()
