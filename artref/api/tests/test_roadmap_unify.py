"""roadmap ↔ profiles 일원화 테스트 — 중복 제거(SSOT) + 풍경 축 diagram 키 + 실제 SVG 존재.
실행: artref/api 에서  python -m tests.test_roadmap_unify
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# roadmap 는 import 시 DB 엔진을 만든다(create_engine 은 lazy — 연결은 안 함). 컨테이너엔 .env 가 있고,
# 단독 실행을 위해 필수 설정만 더미로 채운다(이미 있으면 유지 → 컨테이너 동작 불변).
for _k, _v in {"DB_DSN": "sqlite://", "S3_ENDPOINT": "x", "S3_KEY": "x",
               "S3_SECRET": "x", "EMBEDDING_MODEL": "x"}.items():
    os.environ.setdefault(_k, _v)

from pipeline import roadmap as RM
from pipeline import profiles as P
from pipeline.diagnose import taxonomy

_CONSTRUCTION = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "construction")
LANDSCAPE = {"linear_perspective", "atmospheric_perspective", "depth_layering", "horizon_placement"}


def t_curriculum_is_single_source():
    # roadmap 이 인물 순서를 재정의하지 않고 profiles 를 그대로 참조(같은 객체 → drift 불가)
    assert RM.CURRICULUM is P.FIGURE_ORDER, "CURRICULUM 이 profiles.FIGURE_ORDER 와 다른 객체(중복)"


def t_diagram_key_covers_all_axes():
    assert set(RM.DIAGRAM_KEY) == set(P.ALL_AXES), "DIAGRAM_KEY 가 전체 축과 불일치"
    assert len(RM.DIAGRAM_KEY) == 14, len(RM.DIAGRAM_KEY)
    for a in LANDSCAPE:
        assert RM.DIAGRAM_KEY.get(a) == a, f"풍경 축 {a} 에 diagram 키 없음"


def t_diagram_files_exist():
    # DIAGRAM_KEY 의 모든 값이 실제 construction/<name>.svg 로 존재(없는 파일 가리키지 않음)
    missing = [v for v in RM.DIAGRAM_KEY.values()
               if not os.path.exists(os.path.join(_CONSTRUCTION, f"{v}.svg"))]
    assert not missing, f"construction SVG 누락: {missing}"


def t_step_landscape_has_diagram_and_obs():
    tax = taxonomy()
    for a in LANDSCAPE:
        st = RM._step(a, tax)
        assert st["diagram"] == a, (a, st["diagram"])
        assert st["what_to_observe"] and st["reference_query"], a


def t_focus_over_scene_curriculum():
    # 풍경 커리큘럼에서 첫 미이수 축이 잡힘(구조 먼저 = 구도)
    cur = P.SCENE_ORDER
    current, nxt, statuses = RM._focus_and_next({}, set(), {}, cur)
    assert current in cur and current == "composition_balance", current
    assert set(statuses) == set(cur)


def t_all_axes_order_preserved():
    # ALL_AXES = 인물 10 + 풍경 전용 4(순서 보존, 중복 없음)
    assert P.ALL_AXES[:10] == P.FIGURE_ORDER
    assert set(P.ALL_AXES[10:]) == LANDSCAPE
    assert len(P.ALL_AXES) == len(set(P.ALL_AXES)) == 14


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — SSOT·diagram커버·SVG존재·풍경step·scene focus·순서")


if __name__ == "__main__":
    run()
