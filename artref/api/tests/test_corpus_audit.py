"""corpus_audit 순수 로직 테스트 — DB·Qdrant·CLIP 없이 주입으로 검증.
실행: artref/api 에서  python -m tests.test_corpus_audit
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import corpus_audit as CA

# 작은 가짜 taxonomy(축↔persona↔reference_query)
TAX = {
    "value_structure": {"personas": ["light", "technique"], "reference_query": "value study"},
    "hand_structure": {"personas": ["hand", "anatomy"], "reference_query": "hand reference"},
    "color_harmony": {"personas": ["color"], "reference_query": "color palette"},
}


def make_search(scores_by_query, hand_region_scores=None):
    """search_fn(query, persona, filters, sub_problem) → [(id, score)]. filters region=hand 면 별도 점수."""
    def fn(query, persona, filters, sub_problem):
        if filters and filters.get("region") == "hand":
            s = (hand_region_scores or {}).get(query)
            return [("h1", s)] if s is not None else []
        s = scores_by_query.get(query)
        return [("r1", s)] if s is not None else []
    return fn


def is_miss(hits):
    # search.is_miss 의 단순화: 비었거나 top<0.22 면 miss
    return (not hits) or hits[0][1] < 0.22


def t_axis_probe_hit_and_miss():
    search = make_search({"value study": 0.31, "color palette": 0.10},
                         hand_region_scores={"hand reference": 0.28})
    probe = CA.axis_probe(TAX, search, is_miss)
    by = {p["axis"]: p for p in probe}
    assert by["value_structure"]["miss"] is False and by["value_structure"]["n_hits"] == 1
    assert by["color_harmony"]["miss"] is True            # 0.10 < 0.22
    assert by["hand_structure"]["miss"] is False          # region=hand 필터로 0.28


def t_axis_probe_hand_fallback_when_no_region():
    # region=hand 결과 없음 → 필터 없이 폴백, 그 점수로 판정
    search = make_search({"hand reference": 0.25}, hand_region_scores={})
    probe = CA.axis_probe(TAX, search, is_miss)
    hand = next(p for p in probe if p["axis"] == "hand_structure")
    assert hand["miss"] is False and hand["top_score"] == 0.25


def t_supply_by_axis():
    rows = [
        (["light"], "museum", None),
        (["light", "technique"], "ai_example", None),
        (["hand", "anatomy"], "self_render", "hand"),
        (["color"], "museum", None),
        (["pose"], "self_render", "full"),     # 어느 축 persona 와도 안 겹침(무시)
    ]
    sup = CA.supply_by_axis(TAX, rows)
    assert sup["value_structure"]["total"] == 2
    assert sup["value_structure"]["by_source"] == {"museum": 1, "ai_example": 1}
    assert sup["hand_structure"]["total"] == 1 and sup["hand_structure"]["region_hand"] == 1
    assert sup["color_harmony"]["total"] == 1


def t_backbone_material_counts_full_self_render():
    # anatomy 공유 → hand_structure 가 self_render 전신/크롭 둘 다 잡지만 backbone 재료는 'full' 만
    rows = [
        (["anatomy", "pose"], "self_render", "full"),   # backbone 재료 O
        (["anatomy", "pose"], "self_render", None),     # backbone 재료 O (region None=전신 취급)
        (["hand", "anatomy"], "self_render", "hand"),   # 크롭 → backbone 재료 X
    ]
    sup = CA.supply_by_axis(TAX, rows)
    assert sup["hand_structure"]["backbone_material"] == 2, sup["hand_structure"]
    assert sup["hand_structure"]["region_hand"] == 1


def t_resolvable_misses():
    rows = [(1, "hand reference", '{"sub_problem":"hand_structure"}'),
            (2, "still missing query", {}),]

    def search(term):
        return [("r1", 0.40)] if term == "hand reference" else [("r2", 0.10)]
    stale = CA.resolvable_misses(rows, search, is_miss)
    assert [s[0] for s in stale] == [1], stale     # id=1 만 이제 검색됨(0.40), id=2 는 여전히 miss
    assert stale[0][2] == 0.40


def t_hand_gate_recommendation():
    probe = [{"axis": "hand_structure", "miss": False}]
    sup = {"hand_structure": {"region_hand": 3}}
    rec = CA.hand_gate_recommendation(probe, sup)
    assert rec["ready"] is True and "켜도" in rec["reason"]

    sup0 = {"hand_structure": {"region_hand": 0}}
    rec0 = CA.hand_gate_recommendation(probe, sup0)
    assert rec0["ready"] is False and "0개" in rec0["reason"]

    probe_miss = [{"axis": "hand_structure", "miss": True}]
    rec_m = CA.hand_gate_recommendation(probe_miss, {"hand_structure": {"region_hand": 2}})
    assert rec_m["ready"] is False and "miss" in rec_m["reason"]


def t_gaps_and_miss_summary():
    probe = [{"axis": "color_harmony", "miss": True, "top_score": 0.1},
             {"axis": "value_structure", "miss": False, "top_score": 0.3}]
    sup = {"color_harmony": {"total": 0, "by_source": {}},
           "value_structure": {"total": 5, "by_source": {"museum": 5}}}
    g = CA.gaps(probe, sup)
    assert len(g) == 1 and g[0]["axis"] == "color_harmony"

    miss = CA.summarize_miss([
        ("hand reference", 7, '{"sub_problem":"hand_structure","top_score":0.1}'),
        ("value study", 2, {"sub_problem": "value_structure"}),
    ])
    assert miss[0]["term"] == "hand reference" and miss[0]["count"] == 7
    assert miss[0]["sub_problem"] == "hand_structure"


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 축probe·hand폴백·공급집계·hand게이트·gaps·miss요약")


if __name__ == "__main__":
    run()
