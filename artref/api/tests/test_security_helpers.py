"""_security 헬퍼 테스트 — 순수 함수, 의존 없음.
실행: artref/api 에서  python -m tests.test_security_helpers
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import _security as SEC


def t_valid_ref_id():
    assert SEC.valid_ref_id("3f2504e0-4f89-41d3-9a0c-0305e82c3301")
    assert not SEC.valid_ref_id("floor:value_structure")
    assert not SEC.valid_ref_id("reference/hand_planes.svg")
    assert not SEC.valid_ref_id("../../etc/passwd")
    assert not SEC.valid_ref_id("")
    assert not SEC.valid_ref_id(None)
    assert not SEC.valid_ref_id("images/x.png")


def t_clean_event():
    assert SEC.clean_event("clicked") == "clicked"
    assert SEC.clean_event("saved") == "saved"
    assert SEC.clean_event("DROP TABLE") is None
    assert SEC.clean_event("tried", SEC.PRACTICE_ACTIONS) == "tried"
    assert SEC.clean_event("clicked", SEC.PRACTICE_ACTIONS) is None


def t_clamp_confidence():
    assert SEC.clamp_confidence(0.5) == 0.5
    assert SEC.clamp_confidence(1.7) == 1.0
    assert SEC.clamp_confidence(-3) == 0.0
    assert SEC.clamp_confidence(None) is None
    assert SEC.clamp_confidence("nope") is None


def t_cors_origins_default_and_env():
    os.environ.pop("CORS_ORIGINS", None)
    assert "http://localhost:5173" in SEC.cors_origins()
    os.environ["CORS_ORIGINS"] = "https://a.com, https://b.com"
    try:
        assert SEC.cors_origins() == ["https://a.com", "https://b.com"]
    finally:
        os.environ.pop("CORS_ORIGINS", None)


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — ref_id검증·이벤트화이트리스트·confidence클램프·CORS")


if __name__ == "__main__":
    run()
