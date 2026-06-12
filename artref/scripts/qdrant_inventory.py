"""qdrant_inventory.py — 적재된 벡터를 Qdrant '하나만' 보고 현황을 요약(MySQL/CLIP 불필요).

언제 쓰나: "지금 Qdrant 에 뭐가 들어 있고, 어느 축이 비었나 / 무엇을 더 채울까"를 *가볍게* 보고 싶을 때.
  - 전체 스택(MySQL·MinIO·CLIP)이 필요한 corpus_audit.py 와 달리, 이건 Qdrant payload 만 읽는다.
  - 검색 점수(readiness)·miss_log 까지 보려면 corpus_audit.py 를, 노출/CTR 수요는 coverage_report.py 를.

축 매칭은 corpus_audit.supply_by_axis 와 동일: 레퍼런스의 personas 가 축 personas 와 겹치면 그 축의
공급으로 센다(persona = taxonomy 축 ↔ 레퍼런스 연결고리). → 두 도구의 숫자가 어긋나지 않는다.

실행(컨테이너 권장 — .env 의 QDRANT_URL 사용):
    docker compose exec -w /repo api python scripts/qdrant_inventory.py
로컬에서 직접 돌리려면 QDRANT_URL 등 .env 가 환경에 있어야 한다.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, "api")  # /repo 에서 실행 시 api 패키지 경로
import yaml

from stores.vectors import iter_all   # 백엔드 중립(qdrant scroll). vectors 어댑터 재사용.

_TAX_PATH = os.path.join("api", "schema", "taxonomy.yaml")


def _load_axes():
    """taxonomy.yaml → [(axis_id, personas_set)]. diagnose(무거운 의존) import 없이 직접 읽는다."""
    items = yaml.safe_load(open(_TAX_PATH, encoding="utf-8"))
    out = []
    for it in items:
        out.append((it["id"], set(it.get("personas") or [])))
    return out


def summarize(points, axes):
    """points = [(id, payload_dict)] → 요약 dict. 순수 함수(테스트 가능, Qdrant 불필요)."""
    total = 0
    by_source = Counter()
    by_commercial = Counter()
    persona_dist = Counter()
    by_region = Counter()
    by_category = Counter()
    no_persona = 0
    axis_total = {a: 0 for a, _ in axes}
    axis_by_source = {a: Counter() for a, _ in axes}

    for _id, meta in points:
        total += 1
        st = meta.get("source_type", "unknown")
        by_source[st] += 1
        by_commercial[bool(meta.get("commercial_ok", False))] += 1
        ps = meta.get("personas") or []
        if not ps:
            no_persona += 1
        for p in ps:
            persona_dist[p] += 1
        if meta.get("region"):
            by_region[meta["region"]] += 1
        if meta.get("category"):
            by_category[meta["category"]] += 1
        pset = set(ps)
        for axis, axis_personas in axes:
            if axis_personas & pset:
                axis_total[axis] += 1
                axis_by_source[axis][st] += 1

    return {
        "total": total,
        "by_source": dict(by_source),
        "commercial_ok_true": by_commercial.get(True, 0),
        "commercial_ok_false": by_commercial.get(False, 0),
        "persona_dist": dict(persona_dist),
        "by_region": dict(by_region),
        "by_category": dict(by_category),
        "no_persona": no_persona,
        "axis_total": axis_total,
        "axis_by_source": {a: dict(c) for a, c in axis_by_source.items()},
        "empty_axes": [a for a, _ in axes if axis_total[a] == 0],
    }


def _print(rep, axes):
    print(f"\n총 적재 벡터: {rep['total']}개")
    if rep["total"] == 0:
        print("  (Qdrant 컬렉션이 비어 있습니다 — 적재가 안 됐거나 다른 컬렉션입니다.)")
        return

    print("\n소스별:")
    for st, n in sorted(rep["by_source"].items(), key=lambda x: -x[1]):
        print(f"  {st:14} {n:>6}")

    print(f"\ncommercial_ok: True {rep['commercial_ok_true']} / False {rep['commercial_ok_false']}", end="")
    print("  ⚠️ False 가 있으면 상업-클린 원칙 위반(검색 하드필터로 안 나오지만 정리 권장)"
          if rep["commercial_ok_false"] else "  ✅")
    if rep["no_persona"]:
        print(f"  ⚠️ personas 비어 있는 벡터 {rep['no_persona']}개 — 어떤 축에도 안 잡힘(태깅 누락).")

    print("\n축별 공급(persona 매칭) — 적은/빈 축이 보강 1순위:")
    print(f"  {'axis':24}{'total':>6}{'ai':>5}{'museum':>8}{'self':>6}{'기타':>6}")
    print("  " + "-" * 56)
    for axis, _ in axes:
        t = rep["axis_total"][axis]
        bs = rep["axis_by_source"][axis]
        other = t - bs.get("ai_example", 0) - bs.get("museum", 0) - bs.get("self_render", 0)
        flag = "  ← 비었음" if t == 0 else ("  ← 적음" if t < 3 else "")
        print(f"  {axis:24}{t:>6}{bs.get('ai_example',0):>5}{bs.get('museum',0):>8}"
              f"{bs.get('self_render',0):>6}{other:>6}{flag}")

    if rep["by_region"]:
        print("\nregion:", ", ".join(f"{k}={v}" for k, v in sorted(rep["by_region"].items(), key=lambda x: -x[1])))
    if rep["by_category"]:
        top = sorted(rep["by_category"].items(), key=lambda x: -x[1])[:12]
        print("category(상위):", ", ".join(f"{k}={v}" for k, v in top))

    if rep["empty_axes"]:
        print(f"\n비어 있는 축({len(rep['empty_axes'])}): {', '.join(rep['empty_axes'])}")
        print("  → 이 축들이 코칭에 떠도 레퍼런스가 안 붙습니다(가이드 약화). 우선 보강 대상.")
    else:
        print("\n모든 축에 최소 1개 이상 공급 있음. 👍 (적은 축은 위 '← 적음' 참고)")

    print("\n다음 행동:")
    print("  • 검색 점수·miss 까지 보기:  python scripts/corpus_audit.py   (전체 스택 필요)")
    print("  • 노출/CTR 수요 우선순위:    python scripts/coverage_report.py")
    print("  • 비었거나 적은 축 보강:")
    print("      - AI 예제:   python scripts/bria_generate.py gen_plans/feel_axes.json --out gen_out")
    print("                   python scripts/ingest_ai_examples.py gen_out   (QC 통과분만)")
    print("      - 3D 렌더:   python scripts/render_poses.py ...  →  python scripts/render_batch.py ...")
    print("  • 보강 후:    python scripts/resolve_stale_misses.py  (해결된 miss 닫기) → 다시 이 스크립트")


def main():
    axes = _load_axes()
    try:
        points = [(pid, meta) for pid, _vec, meta in iter_all(with_vectors=False)]
    except Exception as e:
        print(f"[inventory] Qdrant 조회 실패: {type(e).__name__}: {e}")
        print("  QDRANT_URL 이 맞는지, 컬렉션 이름(QDRANT_COLLECTION)이 맞는지 확인하세요.")
        sys.exit(1)
    rep = summarize(points, axes)
    _print(rep, axes)


if __name__ == "__main__":
    main()
