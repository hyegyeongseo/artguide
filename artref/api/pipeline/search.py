import random
from qdrant_client.models import Filter, FieldCondition, MatchValue
from stores.vectors import qc
from cache import text_vec
from config import settings
from pipeline.feedback import adoption_bonus, impressions

# persona → 우선 source_type (HARD 필터 아님, 가산 부스트)
SOURCE_PREF = {"pose": "self_render", "anatomy": "self_render", "hand": "self_render",
               "light": "museum", "color": "museum", "style": "museum", "mood": "museum"}
BROAD_K, SRC_BOOST, PERSONA_BOOST = 50, 0.06, 0.05
COLD_IMPR, EXPLORE_BONUS = 3, 0.07   # 노출<COLD_IMPR인 새 ref를 가끔 끌어올림(수렴 방지)

def search_text(query, persona=None, k=8, filters=None, sub_problem=None, explore=0.15):
    """진단 관찰의 reference_query로 검색. commercial_ok + 선택 filters는 hard,
    source/persona는 soft boost. filters 예: {"gender":"female","region":"hand"}.
    sub_problem 주면 (sub_problem, ref)별 채택/CTR 리랭크 + 콜드스타트 탐색 적용."""
    qvec = text_vec(query)
    must = [FieldCondition(key="commercial_ok", match=MatchValue(value=True))]
    for fkey, fval in (filters or {}).items():
        if fval is not None and fval != "":
            must.append(FieldCondition(key=fkey, match=MatchValue(value=fval)))
    flt = Filter(must=must)
    # 최신 qdrant-client 호환: 권장 API query_points (.search는 deprecated/제거될 수 있음).
    res = qc.query_points(settings.qdrant_collection, query=qvec.tolist(),
                          query_filter=flt, limit=BROAD_K, with_payload=True)
    hits = res.points
    pref, scored = SOURCE_PREF.get(persona), []
    for h in hits:
        s, pl = h.score, (h.payload or {})
        if pref and pl.get("source_type") == pref:
            s += SRC_BOOST
        if persona and persona in (pl.get("personas") or []):
            s += PERSONA_BOOST
        # 1·2단계: (sub_problem, ref)별 채택/CTR 리랭크 (잘 채택 ↑, 자주 떴는데 안 눌림 ↓)
        s += adoption_bonus(sub_problem, h.id)
        # 콜드스타트·탐색: 노출 적은 새 ref에 가끔 작은 보너스 → 소수 ref 수렴 방지
        if explore and impressions(h.id) < COLD_IMPR and random.random() < explore:
            s += EXPLORE_BONUS
        scored.append((h.id, s))
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
