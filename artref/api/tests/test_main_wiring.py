"""main.py 보안 배선 회귀 가드 — fastapi/CLIP 없이(소스 파싱만) 패치가 살아있는지 확인.

main.py 는 import 시 무거운 의존(CLIP·mediapipe·LLM)을 끌어와 단위 테스트에서 import 가 어렵다.
그래서 *소스를 파싱* 해 _security/routes_ai_qc 가 실제로 연결돼 있는지만 검사한다. 누가 패치를 되돌리면
이 테스트가 깨진다(B-1~B-4 + 라우터 마운트 회귀 방지). 런타임 동작 확인은 scripts/smoke_security.py.

실행: artref/api 에서  python -m tests.test_main_wiring
"""
import os
import ast

_MAIN = os.path.join(os.path.dirname(__file__), "..", "main.py")
_SRC = open(_MAIN, encoding="utf-8").read()
_TREE = ast.parse(_SRC)


def _imports():
    """{module: {name,...}} — from X import a,b 형태 수집."""
    out = {}
    for n in ast.walk(_TREE):
        if isinstance(n, ast.ImportFrom) and n.module:
            out.setdefault(n.module, set()).update(a.name for a in n.names)
    return out


def t_security_helpers_imported():
    imp = _imports()
    assert {"valid_ref_id", "clean_event", "clamp_confidence", "cors_origins",
            "PRACTICE_ACTIONS"} <= imp.get("_security", set()), imp.get("_security")
    assert "UploadRejected" in imp.get("ml.upload_guard", set())
    assert "router" in imp.get("routes_ai_qc", set()) or "ai_qc_router" in _SRC


def t_b2_cors_from_env():
    assert "allow_origins=cors_origins()" in _SRC, "CORS 가 cors_origins() 가 아님(하드코딩 회귀)"


def t_b1_upload_rejected_handled():
    assert "except UploadRejected" in _SRC, "UploadRejected 거부 처리 누락(B-1)"


def t_b3_ref_id_validated():
    # /image·/svg·/guide-asset 3곳에서 valid_ref_id 사용(import 제외 ≥3회)
    assert _SRC.count("valid_ref_id(") >= 3, "valid_ref_id 호출이 3곳 미만(B-3)"


def t_b4_event_and_action_validated():
    assert "clean_event(e.event)" in _SRC, "/adopt 이벤트 검증 누락(B-4)"
    assert "clean_event(e.action, PRACTICE_ACTIONS)" in _SRC, "/practice 액션 검증 누락(B-4)"
    assert "clamp_confidence(e.confidence)" in _SRC, "/practice confidence 클램프 누락(B-4)"


def t_ai_qc_router_mounted():
    assert "include_router(ai_qc_router)" in _SRC, "ai_qc 라우터 마운트 누락"


def t_stream_uses_guardrails_not_raw_tokens():
    # /guide/stream 이 가드레일 통과 경로(run_guide)를 쓰고, raw LLM 토큰을 흘리지 않는지.
    #   누가 raw 스트리밍으로 되돌리면(가드레일 우회) 이 테스트가 깨진다.
    assert "run_guide(" in _SRC, "run_guide 미사용(가드레일 경로 우회 회귀)"
    assert "for tok in llm.stream(prompt)" not in _SRC, "raw 토큰 스트리밍 회귀(가드레일 우회)"


def t_access_control_middleware_wired():
    # 인증·레이트리밋 미들웨어가 살아있는지(둘 다 env opt-in).
    assert "is_authorized(" in _SRC, "인증 미들웨어 배선 누락"
    assert "_limiter.allow(" in _SRC, "레이트리밋 미들웨어 배선 누락"


def t_cold_start_applied():
    # 콜드스타트 진입점 교정(업로드=경로설정 트리거)이 파이프라인에 연결됐는지.
    assert "apply_cold_start(" in _SRC, "콜드스타트 진입점 교정 누락"


def t_main_parses():
    assert _TREE is not None  # ast.parse 성공 = 문법 OK


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — _security 배선·CORS·UploadRejected·refid·event·router")


if __name__ == "__main__":
    run()
