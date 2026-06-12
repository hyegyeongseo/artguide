"""test_ai_storage.py — 생성형 AI(ai_example) 적재/검색 게이트/바이어스 순수 로직 회귀.

DB·벡터DB 없이 도는 순수 로직만 검증한다(필터 게이트·Pinecone 변환·ai 그룹핑·병합 선택).
"""
from stores._vecfilter import pinecone_filter
from pipeline._searchlogic import (build_filters, boost,
                                   SRC_BOOST, PERSONA_BOOST, MEDIUM_BOOST, TRACK_BOOST)
from pipeline import asset_index as AI
from pipeline import assets as A


def t_pinecone_filter():
    f = pinecone_filter({"commercial_ok": True}, {"source_type": "ai_example"})
    assert f == {"commercial_ok": {"$eq": True}, "source_type": {"$ne": "ai_example"}}, f
    assert pinecone_filter({"region": ["hand", "arm"]}, None) == {"region": {"$in": ["hand", "arm"]}}
    assert pinecone_filter(None, None) is None


def t_construction_gate():
    # 형태 persona(pose/anatomy/hand) → ai_example 제외(hard)
    for p in ("pose", "anatomy", "hand"):
        assert build_filters(p)[1] == {"source_type": "ai_example"}, p
    # 렌더링 persona → 차단 안 함
    for p in ("light", "color", "style", None):
        assert build_filters(p)[1] == {}, p


def t_filters_merge():
    must, _ = build_filters("light", {"gender": "female", "x": None, "y": ""})
    assert must == {"commercial_ok": True, "gender": "female"}, must   # None/빈값은 무시


def t_soft_bias():
    meta = {"source_type": "museum", "personas": ["light"], "medium": "digital", "track": "anime"}
    b = boost(meta, persona="light", medium="digital", track="anime")
    assert abs(b - (SRC_BOOST + PERSONA_BOOST + MEDIUM_BOOST + TRACK_BOOST)) < 1e-9, b
    assert boost({"source_type": "stock"}, persona="light") == 0.0    # stock(Unsplash)은 비선호 → 0
    assert boost({"medium": "digital"}, medium="watercolor") == 0.0   # 매체 불일치 → 가산 없음


def t_ai_grouping_excludes_construction():
    rows = [("ai_light_001", '{"supports":["light_direction","color_harmony"],"caption":"림"}'),
            ("ai_bad_001", {"supports": ["hand_structure", "value_structure"]})]
    g = AI._ai_candidates_from_rows(rows)
    assert set(g) == {"light_direction", "color_harmony", "value_structure"}, set(g)
    assert "hand_structure" not in g                          # AI_AVOID 축은 제외
    c = g["light_direction"][0]
    assert c["type"] == "ai_example" and c["label"] == "AI 예시" and c["ref_id"] == "ai_light_001"


def t_merge_prefers_ai_on_light():
    AI.clear_cache()
    AI._load_index = lambda: {}
    AI._load_reference_index = lambda: {
        "light_direction": [{"type": "svg", "ref_id": "reference/cast_shadow.svg", "label": "도식", "caption": ""}]}
    AI._load_ai_index = lambda: {
        "light_direction": [{"type": "ai_example", "ref_id": "ai_light_001", "label": "AI 예시", "caption": "림"}]}
    idx = AI.build_asset_index(["light_direction"])
    chosen = A.pick("light_direction", loaded=idx["light_direction"])
    assert chosen["type"] == "ai_example", chosen                # AXIS_PREF[light]=[AI,SVG] → ai 우선


def t_value_axis_prefers_svg_ai_fallback():
    AI.clear_cache()
    AI._load_index = lambda: {}
    AI._load_reference_index = lambda: {
        "value_structure": [{"type": "svg", "ref_id": "reference/value_scale.svg", "label": "도식", "caption": ""}]}
    AI._load_ai_index = lambda: {
        "value_structure": [{"type": "ai_example", "ref_id": "ai_val_001", "label": "AI 예시", "caption": ""}]}
    idx = AI.build_asset_index(["value_structure"])
    chosen = A.pick("value_structure", loaded=idx["value_structure"])
    assert chosen["type"] == "svg", chosen                       # AXIS_PREF[value]=[SVG,AI] → svg 우선, ai 폴백


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(fns)}개) — ai_example 게이트·Pinecone변환·바이어스·병합선택")


if __name__ == "__main__" or True:
    _run()
