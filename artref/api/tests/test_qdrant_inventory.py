"""qdrant_inventory.summarize 회귀 테스트 — Qdrant 없이 순수 집계 로직만.

축 매칭이 corpus_audit.supply_by_axis 와 같은 의미(persona 교집합)인지 고정한다.
실행: artref/api 에서  python -m tests.test_qdrant_inventory
"""
import os
import sys
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# iter_all import 가 config(env) 를 요구 → 테스트용 더미 env.
for k, v in dict(DB_DSN="x://y", S3_ENDPOINT="http://x", S3_KEY="k", S3_SECRET="s",
                 EMBEDDING_MODEL="m", QDRANT_URL="http://localhost:6333").items():
    os.environ.setdefault(k, v)

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "qdrant_inventory.py")
_spec = importlib.util.spec_from_file_location("qdrant_inventory", _PATH)
qi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qi)

AXES = [
    ("weight_balance", {"pose", "anatomy"}),
    ("color_harmony", {"color"}),
    ("hand_structure", {"hand", "anatomy"}),
    ("composition_balance", {"composition"}),
]

PTS = [
    ("id1", {"source_type": "museum", "commercial_ok": True, "personas": ["pose", "anatomy"]}),
    ("id2", {"source_type": "self_render", "commercial_ok": True, "personas": ["pose"], "region": "full"}),
    ("id3", {"source_type": "ai_example", "commercial_ok": True, "personas": ["color"]}),
    ("id4", {"source_type": "museum", "commercial_ok": False, "personas": []}),
]


def t_totals_and_sources():
    r = qi.summarize(PTS, AXES)
    assert r["total"] == 4
    assert r["by_source"] == {"museum": 2, "self_render": 1, "ai_example": 1}


def t_commercial_and_persona_flags():
    r = qi.summarize(PTS, AXES)
    assert r["commercial_ok_false"] == 1 and r["commercial_ok_true"] == 3
    assert r["no_persona"] == 1                 # id4 personas 빈 값


def t_axis_match_is_persona_intersection():
    r = qi.summarize(PTS, AXES)
    # weight_balance{pose,anatomy} ∩ : id1(pose,anatomy), id2(pose) → 2
    assert r["axis_total"]["weight_balance"] == 2
    # hand_structure{hand,anatomy} ∩ : id1(anatomy) → 1
    assert r["axis_total"]["hand_structure"] == 1
    assert r["axis_total"]["color_harmony"] == 1


def t_empty_axes_listed():
    r = qi.summarize(PTS, AXES)
    assert "composition_balance" in r["empty_axes"]   # composition persona 없음
    assert "weight_balance" not in r["empty_axes"]


def t_empty_corpus():
    r = qi.summarize([], AXES)
    assert r["total"] == 0 and len(r["empty_axes"]) == len(AXES)


def t_axis_by_source_breakdown():
    r = qi.summarize(PTS, AXES)
    assert r["axis_by_source"]["weight_balance"].get("museum") == 1
    assert r["axis_by_source"]["weight_balance"].get("self_render") == 1


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 소스집계·플래그·persona교집합 축매칭·빈축")


if __name__ == "__main__":
    run()
