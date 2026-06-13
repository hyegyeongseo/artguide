"""backfill_select.py — 백필 루프의 '계획(plan)' 단계.

현재 검색 readiness(약한 축)를 보고, plan 에서 '약한 축에 해당하는 항목'만 골라
절차적/Imagen 으로 나눠 _todo 파일로 emit 한다. **이미 충분한 축은 건너뛰어** 불필요한 생성을 막는다.

★ 라이브 /guide 와 분리된 *오프라인 잡* 이다. 코칭 요청 경로에서는 절대 생성하지 않는다(BACKFILL.md 참고).
   corpus_audit.py 와 동일한 배선(taxonomy + search_text + axis_probe)을 사용한다.

실행(컨테이너 — CLIP/Qdrant 접근 필요):
  docker compose exec -w /repo api python scripts/backfill_select.py \
      gen_plans/coverage_fill.json --threshold 0.30 --out gen_plans

산출:
  <out>/_todo_procedural.json   # 약한 축 ∩ gen=procedural
  <out>/_todo_imagen.json       # 약한 축 ∩ gen=imagen
그다음:
  imagen  → python scripts/imagen_generate.py <out>/_todo_imagen.json --out /tmp/gen_out
  procedural → python scripts/procedural_generate.py <out>/_todo_procedural.json --out /tmp/gen_out
  적재    → python scripts/ingest_ai_examples.py /tmp/gen_out --state /tmp/gen_out/_ingest_state.txt
"""
import sys
import os
import json
import argparse

sys.path.insert(0, "api")   # /repo 에서 실행 시 api 패키지 경로(corpus_audit.py 와 동일)
from pipeline.diagnose import taxonomy
from pipeline.search import search_text, is_miss
from pipeline import corpus_audit as CA


def _search_fn(query, persona, filters=None, sub_problem=None):
    return search_text(query, persona, filters=filters, sub_problem=sub_problem)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="태깅된 plan(gen 필드 포함) — 예: gen_plans/coverage_fill.json")
    ap.add_argument("--threshold", type=float, default=0.30,
                    help="top_score 이 이 값 미만이면 '약한 축'으로 간주(기본 0.30)")
    ap.add_argument("--out", default="gen_plans", help="_todo 파일 출력 폴더")
    args = ap.parse_args()

    tax = taxonomy()
    try:
        probe = CA.axis_probe(tax, _search_fn, is_miss)
    except Exception as e:
        print(f"검색 probe 실패(Qdrant/CLIP 확인): {type(e).__name__}: {e}")
        sys.exit(1)

    weak = set()
    for p in probe:
        ts = p.get("top_score")
        if p.get("miss") or (ts is not None and ts < args.threshold):
            weak.add(p["axis"])
    print(f"약한 축({len(weak)}, top_score<{args.threshold} 또는 miss): {sorted(weak) or '없음'}")

    plan = json.load(open(args.plan, encoding="utf-8-sig"))
    proc, img = [], []
    for it in plan:
        if not (set(it.get("axes", [])) & weak):
            continue                                  # 이미 충분한 축 → 생성 안 함(중복 방지)
        (proc if it.get("gen") == "procedural" else img).append(it)

    os.makedirs(args.out, exist_ok=True)
    pp = os.path.join(args.out, "_todo_procedural.json")
    ip = os.path.join(args.out, "_todo_imagen.json")
    json.dump(proc, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(img,  open(ip, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def s(x):
        return sum(i.get("n", 1) for i in x)
    print(f"절차적 todo: {len(proc)}항목 / {s(proc)}장 → {pp}")
    print(f"Imagen todo: {len(img)}항목 / {s(img)}장 → {ip}")
    if not weak:
        print("\n약한 축 없음 — 지금은 백필할 필요 없습니다. 👍 (feel 축 topScore 가 충분)")


if __name__ == "__main__":
    main()
