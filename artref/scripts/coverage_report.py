"""coverage_report.py — 피드백이 '다음에 뭘 렌더할지' 알려주게(3단계).

sub_problem별로 노출·채택·CTR과 self_render 보유량을 모아 렌더 우선순위를 매긴다.
수요(노출) 높은데 CTR 낮거나 self_render가 적은 sub_problem = 라이브러리 보강 시급.

실행:
    docker compose exec -w /repo api python scripts/coverage_report.py
"""
import sys, json
from collections import Counter

sys.path.insert(0, "api")  # /repo에서 실행 시 api 패키지 경로
from sqlalchemy import text
from stores.db import engine
from pipeline.diagnose import taxonomy


def main():
    with engine.begin() as cx:
        impr = {sp: n for sp, n in cx.execute(text(
            "SELECT sub_problem, COUNT(*) FROM adoption_log "
            "WHERE event='shown' AND sub_problem IS NOT NULL GROUP BY sub_problem"))}
        pos = {sp: n for sp, n in cx.execute(text("""
            SELECT s.sub_problem, COUNT(*) FROM adoption_log a
            JOIN (SELECT DISTINCT guide_id, reference_id, sub_problem FROM adoption_log
                  WHERE event='shown' AND sub_problem IS NOT NULL) s
              ON a.guide_id=s.guide_id AND a.reference_id=s.reference_id
            WHERE a.event IN ('clicked','saved','liked') GROUP BY s.sub_problem"""))}
        # persona별 self_render 보유량
        cnt = Counter()
        for personas_json, st in cx.execute(text(
                "SELECT personas, source_type FROM reference_images")):
            try:
                ps = json.loads(personas_json) if personas_json else []
            except Exception:
                ps = []
            for p in ps:
                cnt[(p, st)] += 1

    tax = taxonomy()
    rows = []
    for sp, e in tax.items():
        i, p = impr.get(sp, 0), pos.get(sp, 0)
        ctr = (p / i) if i else None
        persona = e["personas"][0]
        sr = cnt.get((persona, "self_render"), 0)
        scarcity = 1.0 / (1 + sr)                       # self_render 적을수록 ↑
        weak = 1 - (ctr if ctr is not None else 0.0)    # CTR 낮을수록 ↑
        priority = i * (0.5 * scarcity + 0.5 * weak)    # 수요 가중
        rows.append((priority, sp, persona, i, p, ctr, sr))
    rows.sort(reverse=True)

    print(f"{'sub_problem':20}{'persona':10}{'노출':>6}{'채택':>6}{'CTR':>7}"
          f"{'self_render':>12}{'우선순위':>10}")
    print("-" * 75)
    for priority, sp, persona, i, p, ctr, sr in rows:
        ctr_s = f"{ctr*100:4.0f}%" if ctr is not None else "  -  "
        print(f"{sp:20}{persona:10}{i:>6}{p:>6}{ctr_s:>7}{sr:>12}{priority:>10.1f}")
    print("\n→ 우선순위 높은 sub_problem의 카테고리부터 render_poses로 더 렌더 → render_batch 적재.")
    print("  (노출 수요는 큰데 self_render가 적거나 CTR이 낮은 영역이 먼저 올라옵니다.)")


if __name__ == "__main__":
    main()
