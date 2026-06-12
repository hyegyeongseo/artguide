import os
import random
from stores import vectors as vstore
from cache import text_vec
from pipeline.feedback import adoption_bonus, impressions
from pipeline._searchlogic import build_filters, boost, SOURCE_PREF  # SOURCE_PREF 재노출(호환)

BROAD_K = 50
COLD_IMPR, EXPLORE_BONUS = 3, 0.07   # 노출<COLD_IMPR인 새 ref를 가끔 끌어올림(수렴 방지)


def search_text(query, persona=None, k=8, filters=None, sub_problem=None,
                explore=0.15, medium=None, track=None):
    """진단 관찰의 reference_query로 검색. commercial_ok + 선택 filters 는 hard,
    형태 persona(pose/anatomy/hand)면 ai_example 제외도 hard. source/persona/medium/track 은 soft boost.
    medium/track = 사용자 맥락(선택) — 같은 매체/스타일을 우선하되 없으면 폴백.
    sub_problem 주면 (sub_problem, ref)별 채택/CTR 리랭크 + 콜드스타트 탐색 적용."""
    qvec = text_vec(query)
    must, must_not = build_filters(persona, filters)
    hits = vstore.query(qvec.tolist(), BROAD_K, must=must, must_not=must_not)
    scored = []
    for h in hits:
        s = h.score + boost(h.meta, persona, medium, track)
        # (sub_problem, ref)별 채택/CTR 리랭크 (잘 채택 ↑, 자주 떴는데 안 눌림 ↓)
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
