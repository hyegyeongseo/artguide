"""pipeline/corpus_audit.py — 코퍼스 '검색 준비 상태' 감사(공급 기반, 트래픽 불필요).

기존 scripts/coverage_report.py 는 *수요 기반*(노출·CTR → 렌더 우선순위)이라 트래픽이 쌓여야
의미가 있다. 이 모듈은 그 반대 — *적재 직후* "지금 코퍼스로 모든 taxonomy 축이 실제로 검색되나",
"어느 축/region/source_type 이 비었나"를 트래픽 없이 본다. 다음 질문에 답한다:

  1) 축별 검색 readiness : 각 sub_problem 의 reference_query 를 *앱과 같은* search 로 던져 top score·
     hit 수·miss 여부를 본다(손 축은 region=hand 필터까지 — main.py 와 동일). → "비어 보이는 축" 식별.
  2) 공급 인벤토리        : reference_images 를 축×source_type×region 으로 집계. backbone_3d/ai_example/
     museum/self_render 가 어디에 있고 어디가 0인지.
  3) 손 게이트 점검      : hand_structure 가 region=hand 레퍼런스를 갖고 잘 검색되면 HAND_AUTO 켜도 됨을
     알려준다(배치1에서 hand_signal 을 HAND_AUTO 로 게이트한 그 전제 조건을 데이터로 확인).
  4) miss 요약           : miss_log(있으면) 미해결 term 을 count 순으로 — '무엇을 더 렌더/적재할지'.

순수 로직은 전부 *주입 가능*(search_fn·is_miss_fn·rows)이라 DB·Qdrant·CLIP 없이 테스트된다.
CLI(scripts/corpus_audit.py)가 실제 search_text/engine 을 붙여 돌린다.
"""
from collections import Counter


def axis_probe(taxonomy, search_fn, is_miss_fn, k=8):
    """각 축의 reference_query 로 검색 → readiness. 반환: [{axis, persona, top_score, n_hits, miss}].

    search_fn(query, persona, filters, sub_problem) -> [(ref_id, score), ...] (search_text 시그니처 일부).
    손 축은 region=hand 필터로 던지고, 비면 필터 없이 폴백(main.py 와 동일한 의미).
    """
    out = []
    for axis, e in taxonomy.items():
        persona = (e.get("personas") or [None])[0]
        rq = e.get("reference_query") or axis
        f = {"region": "hand"} if axis == "hand_structure" else None
        hits = search_fn(rq, persona, f, axis)
        if not hits and f:
            hits = search_fn(rq, persona, None, axis)
        top = float(hits[0][1]) if hits else None
        out.append({"axis": axis, "persona": persona,
                    "top_score": round(top, 4) if top is not None else None,
                    "n_hits": len(hits), "miss": bool(is_miss_fn(hits))})
    return out


def supply_by_axis(taxonomy, rows):
    """rows: [(personas_list, source_type, region)] → 축별 보유량.

    축의 personas 와 겹치는 레퍼런스를 그 축의 공급으로 본다(persona = taxonomy 축↔레퍼런스 연결고리).
    반환: {axis: {total, by_source:{...}, region_hand, backbone_material}}.

    backbone_material = self_render 전신(region None/'full') 수. backbone_3d guide-asset 은
    *source_type 이 아니라* 이 self_render 행들에서 파생되므로(asset_index), 'backbone:0' 오해를 막기
    위해 따로 센다. (region=hand 크롭은 backbone 아님 → 제외.)
    """
    out = {}
    for axis, e in taxonomy.items():
        personas = set(e.get("personas") or [])
        sel = [r for r in rows if personas & set(r[0] or [])]
        out[axis] = {
            "total": len(sel),
            "by_source": dict(Counter(r[1] for r in sel)),
            "region_hand": sum(1 for r in sel if r[2] == "hand"),
            "backbone_material": sum(1 for r in sel
                                     if r[1] == "self_render" and r[2] in (None, "full")),
        }
    return out


def hand_gate_recommendation(probe, supply):
    """HAND_AUTO 를 켜도 되는지(배치1 게이트의 전제). region=hand 레퍼런스가 있고 손 검색이 miss 가
    아니면 권장. 반환: {ready: bool, reason: str, region_hand: int, miss: bool|None}."""
    rh = supply.get("hand_structure", {}).get("region_hand", 0)
    pm = next((p for p in probe if p["axis"] == "hand_structure"), None)
    miss = pm["miss"] if pm else None
    ready = rh > 0 and miss is False
    if rh == 0:
        reason = "region=hand 레퍼런스 0개 → 손 신호가 떠도 검색이 전부 miss. HAND_AUTO 끄세요."
    elif miss:
        reason = f"region=hand 레퍼런스 {rh}개 있으나 손 reference_query 검색이 miss → 매칭 점검 후 켜기."
    else:
        reason = f"region=hand 레퍼런스 {rh}개 + 검색 OK → HAND_AUTO=1 켜도 됩니다."
    return {"ready": ready, "reason": reason, "region_hand": rh, "miss": miss}


def summarize_miss(miss_rows, top=15):
    """miss_log rows: [(term, count, context_dict_or_str)] → count 순 상위. context 의 sub_problem 노출."""
    import json
    out = []
    for term, count, ctx in miss_rows:
        if isinstance(ctx, str):
            try:
                ctx = json.loads(ctx)
            except Exception:
                ctx = {}
        ctx = ctx or {}
        out.append({"term": term, "count": int(count or 0),
                    "sub_problem": ctx.get("sub_problem"),
                    "measured": ctx.get("measured"),
                    "top_score": ctx.get("top_score")})
    out.sort(key=lambda r: -r["count"])
    return out[:top]


def gaps(probe, supply):
    """사람이 읽을 '비었거나 약한' 축 목록. miss 이거나 공급 0/floor-only 인 축을 모은다."""
    g = []
    for p in probe:
        axis = p["axis"]
        sup = supply.get(axis, {})
        total = sup.get("total", 0)
        if p["miss"] or total == 0:
            g.append({"axis": axis, "miss": p["miss"], "top_score": p["top_score"],
                      "supply_total": total, "by_source": sup.get("by_source", {})})
    return g


def resolvable_misses(miss_rows, search_fn, is_miss_fn):
    """miss_log 의 미해결 term 중, 코퍼스가 보강돼 *이제는 잘 검색되는* 것(stale)을 찾는다.

    miss_rows: [(id, term, context_dict_or_str)] → resolved 로 표시할 [(id, term, top_score)].
    search_fn(term) -> [(ref_id, score)]. 적재 후 옛 miss 가 더는 miss 가 아니면 정리 대상.
    """
    import json
    out = []
    for mid, term, ctx in miss_rows:
        if isinstance(ctx, str):
            try:
                ctx = json.loads(ctx)
            except Exception:
                ctx = {}
        try:
            hits = search_fn(term)
        except Exception:
            continue
        if not is_miss_fn(hits):
            out.append((mid, term, float(hits[0][1]) if hits else None))
    return out
