import os
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


# ── miss 판정 ─────────────────────────────────────────────────────────────
# 검색이 '사실상 실패'했는지 판단해 라이브러리 보강 큐(miss_log)로 보낼지 정한다.
# OpenCLIP ViT-B-32 text→image 코사인은 좋은 매치도 보통 0.25~0.35 수준이라
# 임계값은 보수적으로 잡고 env로 조정 가능하게 둔다(컬렉션 채워지면 재튜닝).
MISS_SCORE_MIN = float(os.environ.get("MISS_SCORE_MIN", "0.22"))  # top hit 코사인 하한
MISS_MIN_HITS  = int(os.environ.get("MISS_MIN_HITS", "1"))        # 최소 결과 수

def top_score(hits):
    return hits[0][1] if hits else None

def is_miss(hits):
    """결과가 비었거나(또는 너무 적거나) 최고 점수가 낮으면 miss → 렌더로 보강할 대상."""
    if len(hits) < MISS_MIN_HITS:
        return True
    return hits[0][1] < MISS_SCORE_MIN
