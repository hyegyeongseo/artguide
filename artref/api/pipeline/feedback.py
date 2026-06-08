"""pipeline/feedback.py — 채택/노출 로그(adoption_log) 기반 리랭크 신호.

검색 점수에 더할 작은 보너스를 (sub_problem, reference_id)별로 계산한다.
- 채택(clicked/saved/liked) ↑, 자주 노출됐는데 안 눌린 ref ↓ (단순 인기 편향 방지 → CTR성 신호).
- 라플라스 스무딩으로 표본 적은 ref를 기준점(0.2) 근처로(콜드스타트 완화).
- TTL 캐시(매 검색마다 DB 안 침). DB 실패/빈 테이블이면 boost=0 (앱 절대 안 깨짐).
- 노출수(impressions)를 따로 노출해 검색의 탐색(exploration)에 사용.

주의: 이 신호는 '레퍼런스 유용성'에 대한 것이지 사용자 실력 판정이 아니다(앱 원칙 유지).
"""
import time
import threading
from collections import defaultdict
from sqlalchemy import text
from stores.db import engine

_TTL = 60.0  # 초. 집계 캐시 수명.
_lock = threading.Lock()
_cache = {"t": -1e9, "boost": {}, "global_impr": {}}

POS_WEIGHT = {"clicked": 1.0, "saved": 2.0, "liked": 1.5}  # 핀(saved)을 더 강한 신호로
SMOOTH_A, SMOOTH_B = 1.0, 4.0           # 사전분포: 무신호 ref의 기준점 = A/(A+B) = 0.2
BASELINE = SMOOTH_A / (SMOOTH_A + SMOOTH_B)
FB_SCALE = 0.10                          # 점수(코사인≈[-1,1])에 더하는 규모
FB_CAP = 0.12                            # 보너스 상·하한 (지배 방지)


def _recompute():
    boost = defaultdict(dict)            # sub_problem -> ref_id -> 스무딩 점수
    global_impr = defaultdict(int)       # ref_id -> 노출수(모든 sub_problem 합)
    with engine.begin() as cx:
        impr = defaultdict(lambda: defaultdict(int))   # sub_problem -> ref -> 노출수
        for sp, ref, n in cx.execute(text(
                "SELECT sub_problem, reference_id, COUNT(*) FROM adoption_log "
                "WHERE event='shown' GROUP BY sub_problem, reference_id")):
            if sp:
                impr[sp][ref] = n
            global_impr[ref] += n
        # 채택(clicked/saved/liked)은 노출 행과 (guide_id, reference_id)로 조인해 sub_problem 회수
        pos = defaultdict(lambda: defaultdict(float))
        for sp, ref, ev, n in cx.execute(text("""
                SELECT s.sub_problem AS sp, a.reference_id AS ref, a.event AS ev, COUNT(*) AS n
                FROM adoption_log a
                JOIN (SELECT DISTINCT guide_id, reference_id, sub_problem
                      FROM adoption_log WHERE event='shown' AND sub_problem IS NOT NULL) s
                  ON a.guide_id = s.guide_id AND a.reference_id = s.reference_id
                WHERE a.event IN ('clicked','saved','liked')
                GROUP BY s.sub_problem, a.reference_id, a.event""")):
            if sp:
                pos[sp][ref] += POS_WEIGHT.get(ev, 1.0) * n
        for sp in set(impr) | set(pos):
            for ref in set(impr.get(sp, {})) | set(pos.get(sp, {})):
                p = pos.get(sp, {}).get(ref, 0.0)
                i = impr.get(sp, {}).get(ref, 0)
                boost[sp][ref] = (p + SMOOTH_A) / (i + SMOOTH_A + SMOOTH_B)
    return dict(boost), dict(global_impr)


def _ensure():
    if time.time() - _cache["t"] > _TTL:
        with _lock:
            if time.time() - _cache["t"] > _TTL:
                try:
                    b, g = _recompute()
                    _cache.update(t=time.time(), boost=b, global_impr=g)
                except Exception as e:
                    print(f"[feedback] 집계 실패(무시, boost=0): {type(e).__name__}: {e}")
                    _cache["t"] = time.time()  # 다음 TTL까지 빈 캐시 유지(앱 안 깨짐)
    return _cache


def adoption_bonus(sub_problem, ref_id):
    """(sub_problem, ref)의 채택/노출 신호 → 검색 점수 보너스(±FB_CAP)."""
    if not sub_problem:
        return 0.0
    s = _ensure()["boost"].get(sub_problem, {}).get(ref_id)
    if s is None:
        return 0.0
    return max(-FB_CAP, min(FB_CAP, FB_SCALE * (s - BASELINE)))


def impressions(ref_id):
    """ref가 지금까지 몇 번 노출됐는지(탐색 판단용)."""
    return _ensure()["global_impr"].get(ref_id, 0)


def refresh():
    """다음 호출 때 강제 재집계(테스트/즉시 반영용)."""
    _cache["t"] = -1e9
