"""probe_composition.py — composition reference_query 후보 + 임계값 기준선(anchor)을 한 번에 측정.

ViT-L/14(768) 재임베딩이 끝난 뒤 실행하면, 새 모델 기준으로:
  (A) ANCHOR       : 코퍼스가 확실한 축들의 reference_query top 점수 = '정상 적중' 대역(임계값 근거)
  (B) CANDIDATES   : composition 문구 후보별 top 점수 + top3 source(+ museum 우세 표시)
  (C) RECOMMENDATION: anchor 대역에서 도출한 MISS_SCORE_MIN 제안 + 그 임계값을 넘는 최적 문구

⚠ 반드시 재색인 완료 후(= qdrant 포인트수 ≈ reference_images 행수) 실행하세요. 재색인 중이면 점수가 낮게 나옵니다.

실행:
    docker compose exec -w /repo api python scripts/probe_composition.py
추가 후보 직접 넣기:
    docker compose exec -w /repo api python scripts/probe_composition.py "my new phrasing"
임계값을 바꿔 보며 PASS 판정 확인:
    docker compose exec -e MISS_SCORE_MIN=0.18 -w /repo api python scripts/probe_composition.py
"""
import os, sys
sys.path.insert(0, "api")
from cache import text_vec
from stores import vectors as vstore
from pipeline.diagnose import taxonomy

MISS = float(os.environ.get("MISS_SCORE_MIN", "0.22"))

# 정상 적중 기준선용 축 — 코퍼스가 확실한(이전 audit에서 miss 0%) 축들의 실제 reference_query 사용.
#  - self_render 밀집: weight_balance / foreshortening / proportion / joint_articulation
#  - museum 이미지축: light_direction / color_harmony
ANCHOR_AXES = ["weight_balance", "foreshortening", "proportion",
               "joint_articulation", "light_direction", "color_harmony"]

CANDIDATES = [
    "composition rule of thirds focal point placement",        # 현재값(기준선)
    "painting off-center subject open sky negative space",      # 이전 ViT-B/32 우승
    "landscape painting low horizon empty foreground",
    "painting strong focal point empty space around",
    "still life arrangement balanced negative space",
    "wide landscape asymmetric balance",
    "painting subject placed to one side large empty area",
    "minimalist composition single subject vast negative space",
    "scene with clear focal point and surrounding empty space",
]


def _probe(q):
    try:
        hits = vstore.query(text_vec(q).tolist(), 5, must={"commercial_ok": True})
    except Exception as e:
        return None, [], f"{type(e).__name__}: {e}"
    if not hits:
        return None, [], ""
    srcs = [(h.meta or {}).get("source_type", "?") for h in hits[:3]]
    return hits[0].score, srcs, ""


def main():
    tax = taxonomy()
    extra = [a for a in sys.argv[1:] if a.strip()]
    print(f"MISS_SCORE_MIN(current)={MISS}\n")

    # (A) ANCHOR
    print("== (A) ANCHOR — 정상 적중 대역 ==")
    anchor_tops = []
    for ax in ANCHOR_AXES:
        node = tax.get(ax)
        if not node:
            print(f"  {ax:22} (taxonomy에 없음 — 건너뜀)")
            continue
        rq = node.get("reference_query") or ax
        top, srcs, err = _probe(rq)
        if err:
            print(f"  {ax:22} [err] {err}")
            continue
        if top is not None:
            anchor_tops.append(top)
        ts = f"{top:.3f}" if top is not None else "None"
        print(f"  {ax:22} top={ts}  src={','.join(srcs)}")
    print()

    # (B) CANDIDATES
    print("== (B) COMPOSITION CANDIDATES ==")
    results = []
    for q in CANDIDATES + extra:
        top, srcs, err = _probe(q)
        if err:
            print(f"  [err ] {err}  ::  {q}")
            continue
        museum_dom = srcs.count("museum") >= 2
        results.append((q, top, srcs, museum_dom))
        ts = f"{top:.3f}" if top is not None else "None"
        flag = "PASS" if (top is not None and top >= MISS) else "miss"
        tag = "  <museum-dom>" if museum_dom else ""
        print(f"  [{flag}] top={ts}  top3_src={','.join(srcs)}{tag}  ::  {q}")
    print()

    # (C) RECOMMENDATION
    print("== (C) RECOMMENDATION ==")
    if anchor_tops:
        lo, hi = min(anchor_tops), max(anchor_tops)
        suggested = round(lo - 0.02, 3)
        print(f"  anchor 적중 대역: {lo:.3f} ~ {hi:.3f}")
        print(f"  → MISS_SCORE_MIN 제안: {suggested}  (가장 낮은 정상 적중보다 0.02 아래)")
    else:
        suggested = MISS
        print("  anchor 점수 없음 → 재색인/코퍼스 확인 필요. 임계값 제안 보류.")

    usable = [r for r in results if r[1] is not None]
    museum_first = [r for r in usable if r[3]]
    pool = museum_first or usable
    if pool:
        best = max(pool, key=lambda r: r[1])
        verdict = "넘김 ✓" if best[1] >= suggested else "못넘김 ✗"
        print(f"  → 최적 composition reference_query:")
        print(f"       \"{best[0]}\"")
        print(f"       top={best[1]:.3f}  src={','.join(best[2])}  (제안 임계값 {suggested} 대비 {verdict})")
        if not museum_first:
            print("       ⚠ museum 우세 후보 없음 — 점수는 넘어도 그림이 아닌 self_render를 끌어왔을 수 있음. 코퍼스/문구 재검토.")
    print("\n위 (A)(B)(C) 블록 전체를 그대로 붙여주시면, 튜닝된 taxonomy.yaml(zip) + 넣을 MISS_SCORE_MIN 을 만들어 드립니다.")


if __name__ == "__main__":
    main()
