"""라우터(pipeline/router.py) 회귀 테스트 — 트리아지 모드 + 한국어 단어경계 오탐 방지.

한국어는 공백이 없어 '색'⊂'어색', '완성'⊂'미완성' 같은 오탐이 나기 쉽다. 앞경계 규칙이
이걸 막는지 고정한다. 실행: artref/api 에서  python -m tests.test_router
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import router as R

ART_PERSON = {"analyzable": True, "subject": {"person": {"present": True}}}
ART_SCENE = {"analyzable": True, "subject": {"person": {"present": False}}}
NOT_ART = {"analyzable": False}


def t_triage_generate_redirect():
    assert R.triage("이거 그려줘", ART_PERSON) == ("generate", "redirect")
    assert R.triage("make it for me", ART_PERSON)[1] == "redirect"


def t_triage_not_drawing_clarify():
    assert R.triage("이게 뭐야", NOT_ART) == ("not_drawing", "clarify")


def t_triage_score_to_coach():
    cat, mode = R.triage("이거 몇 점이야?", ART_PERSON)
    assert (cat, mode) == ("score", "coach")     # 채점 대신 관찰 코칭으로(금지어는 가드레일이 막음)


def t_triage_offtopic_to_coach():
    cat, mode = R.triage("이거 팔릴까?", ART_PERSON)
    assert (cat, mode) == ("offtopic", "coach")


def t_triage_default_coach():
    assert R.triage("손 좀 봐줘", ART_PERSON) == ("coach", "coach")


def t_detect_terms_boundary_color():
    assert "color_harmony" not in R.detect_terms("이거 좀 어색해요")   # '색'⊂'어색' 오탐 방지
    assert "color_harmony" in R.detect_terms("색감이 어때요")          # 진짜 색 언급
    assert "color_harmony" in R.detect_terms("이 색 괜찮아?")


def t_detect_terms_boundary_value():
    assert "value_structure" not in R.detect_terms("설명도 부탁해요")  # '명도'⊂'설명도' 오탐 방지
    assert "value_structure" in R.detect_terms("명도 대비가 약해요")


def t_detect_terms_hand_and_pose():
    assert "hand_structure" in R.detect_terms("손이 이상해")
    assert "weight_balance" in R.detect_terms("자세 균형 좀")
    assert R.detect_terms("그냥 봐주세요") == set()                    # 부위 언급 없음 → 빈 set


def t_detect_intent_boundary_finished():
    assert R.detect_intent("완성작이에요") == "finished"
    assert R.detect_intent("아직 미완성이에요") != "finished"          # '완성'⊂'미완성' 오탐 방지
    assert R.detect_intent("연습 중이에요") == "practice"
    assert R.detect_intent("") == "open"


def t_detect_intent_explicit_overrides():
    assert R.detect_intent("완성작이에요", explicit="practice") == "practice"
    assert R.detect_intent("아무말", explicit="finished") == "finished"


def t_resolve_personas_and_modes():
    mode, personas, terms = R.resolve("자세 좀 봐줘", ART_PERSON)
    assert mode == "coach" and personas == ["pose", "anatomy"]
    mode, personas, _ = R.resolve("구도 어때", ART_SCENE)
    assert personas == ["composition", "light", "color"]
    assert R.resolve("그려줘", ART_PERSON) == ("redirect", [], set())
    assert R.resolve("이게 뭐야", NOT_ART) == ("clarify", [], set())


def t_resolve_offtopic_empty_terms():
    # offtopic 은 부위 언급 없으니 빈 user_terms(L1 관찰 제안)
    mode, personas, terms = R.resolve("이거 팔릴까?", ART_PERSON)
    assert mode == "coach" and terms == set()


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 트리아지모드·색/명도/완성 경계·persona·offtopic")


if __name__ == "__main__":
    run()
