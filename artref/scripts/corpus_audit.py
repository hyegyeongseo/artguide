"""corpus_audit.py — 적재된 코퍼스의 '검색 준비 상태'를 한 화면에 출력(트래픽 불필요).

기존 coverage_report.py(수요 기반)와 짝이 되는 *공급/검색 readiness* 리포트. render_out 적재 직후
"모든 축이 실제로 검색되나 / 어디가 비었나 / HAND_AUTO 켜도 되나"를 바로 확인한다.

실행(컨테이너 — search 가 CLIP/Qdrant/MySQL 접근):
    docker compose exec -w /repo api python scripts/corpus_audit.py
"""
import sys
import json

sys.path.insert(0, "api")  # /repo 에서 실행 시 api 패키지 경로
from sqlalchemy import text
from stores.db import engine
from pipeline.diagnose import taxonomy
from pipeline.search import search_text, is_miss
from pipeline import corpus_audit as CA


def _search_fn(query, persona, filters, sub_problem):
    return search_text(query, persona, filters=filters, sub_problem=sub_problem)


def _load_rows():
    """reference_images → [(personas_list, source_type, region)]."""
    rows = []
    with engine.begin() as cx:
        for personas_json, st, region in cx.execute(text(
                "SELECT personas, source_type, region FROM reference_images")):
            try:
                ps = json.loads(personas_json) if personas_json else []
            except Exception:
                ps = []
            rows.append((ps, st, region))
    return rows


def _load_miss():
    try:
        with engine.begin() as cx:
            return [(t, c, ctx) for t, c, ctx in cx.execute(text(
                "SELECT term, count, context FROM miss_log WHERE resolved=0 "
                "ORDER BY count DESC LIMIT 50"))]
    except Exception as e:
        print(f"[audit] miss_log 조회 실패(무시): {type(e).__name__}: {e}")
        return []


def main():
    tax = taxonomy()

    # 1) 공급 인벤토리
    try:
        rows = _load_rows()
    except Exception as e:
        print(f"[audit] reference_images 조회 실패: {type(e).__name__}: {e}")
        rows = []
    supply = CA.supply_by_axis(tax, rows)

    # 2) 축별 검색 readiness
    try:
        probe = CA.axis_probe(tax, _search_fn, is_miss)
    except Exception as e:
        print(f"[audit] 검색 probe 실패(Qdrant/CLIP 확인): {type(e).__name__}: {e}")
        probe = []

    print(f"\n총 레퍼런스: {len(rows)}개\n")
    print(f"{'sub_problem':22}{'persona':10}{'공급':>5}{'bb재료':>7}{'ai':>4}"
          f"{'museum':>8}{'self':>6}{'topScore':>10}{'hits':>5}{'miss':>6}")
    print("-" * 95)
    pmap = {p["axis"]: p for p in probe}
    for axis in tax:
        sup = supply.get(axis, {})
        bs = sup.get("by_source", {})
        p = pmap.get(axis, {})
        ts = p.get("top_score")
        print(f"{axis:22}{(tax[axis]['personas'][0]):10}{sup.get('total',0):>5}"
              f"{sup.get('backbone_material',0):>7}{bs.get('ai_example',0):>4}"
              f"{bs.get('museum',0):>8}{bs.get('self_render',0):>6}"
              f"{(f'{ts:.3f}' if ts is not None else '  -  '):>10}"
              f"{p.get('n_hits',0):>5}{('MISS' if p.get('miss') else 'ok'):>6}")
    print("  (bb재료 = self_render 전신 렌더 수 = backbone_3d guide-asset 의 원천. source_type 아님)")

    # 3) 손 게이트 점검
    rec = CA.hand_gate_recommendation(probe, supply)
    print(f"\n[HAND_AUTO] {rec['reason']}")

    # 4) 비었거나 약한 축
    g = CA.gaps(probe, supply)
    if g:
        print("\n비었거나 약한 축(검색 miss 또는 공급 0):")
        for x in g:
            print(f"  - {x['axis']}: miss={x['miss']} top={x['top_score']} "
                  f"공급={x['supply_total']} {x['by_source']}")
    else:
        print("\n모든 축이 검색 가능 + 공급 있음. 👍")

    # 5) miss_log 요약(트래픽 있었으면)
    miss = CA.summarize_miss(_load_miss())
    if miss:
        print("\nmiss_log 상위(무엇을 더 렌더/적재할지):")
        for m in miss:
            print(f"  {m['count']:>4}x  {m['sub_problem'] or '-':22} "
                  f"top={m['top_score']}  '{m['term'][:48]}'")

    print("\n→ MISS/공급0 축부터 보강. 손 축이 ready 면 .env 에 HAND_AUTO=1.")


if __name__ == "__main__":
    main()
