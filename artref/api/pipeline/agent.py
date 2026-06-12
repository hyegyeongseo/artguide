"""Grounded coaching agent — 근거(룰이 낸 후보) 위에서 '무엇을 먼저·어떤 레퍼런스로·어떤 톤으로'를 *선택*한다.

이 모듈이 이 프로젝트의 '에이전트'가 명시적으로 사는 곳이다. 불변식:
  • 룰이 소유 : 사실(진단), 성장 상태, 커리큘럼, 그리고 *후보 집합*(observations · sub_problem별 reference 후보).
  • 에이전트가 소유 : 그 후보 집합 *안에서의* 선택 · 순서 · 톤.
  • 에이전트가 절대 못 함 : 후보 밖 sub_problem/reference를 지어내기, 완성도·성장을 판정하기.

LLM이 켜져 있으면(AGENT_LLM_SELECT) LLM이 후보 중에서 고르고(complete_json), 없거나 출력이 검증을
통과 못 하면 결정적 정책으로 폴백한다. validate()가 모든 선택을 후보와 교집합해 grounding을 강제하므로,
LLM이 무엇을 뱉든 측정 밖의 것은 응답에 못 들어온다(= "환각이 성장에 개입하지 않는다").
"""
import os
import json

from pipeline.profiles import POSE_DEPENDENT

MAX_BLOCKS = 3   # 한 번에 보여줄 최대 블록 수(인지 부하 ↓). diagnose가 이미 상위로 좁혀 둠.


def assemble_context(diagnosis, refs_by_sp, growth, intent, track):
    """룰 산출물을 에이전트가 고를 '후보 묶음'으로 명시화한다(순수 dict)."""
    obs = diagnosis.get("observations", [])
    cand_ids = [o["sub_problem"] for o in obs]                      # 후보 sub_problem(룰 랭킹순)
    ref_cand = {sp: [rid for rid, _ in refs_by_sp.get(sp, [])] for sp in cand_ids}
    g = growth or {}
    return {
        "candidates": cand_ids,
        "obs_by_sp": {o["sub_problem"]: o for o in obs},
        "ref_candidates": ref_cand,
        "degraded": bool(diagnosis.get("degraded")),   # 전신 미검출 → 포즈 축은 측정 불가
        "focus": g.get("current_focus"),
        "recurring": [s for s in g.get("recurring", []) if s in cand_ids],
        "steady": g.get("steady", []),
        "intent": intent,
        "track": track,
    }


def _applicable(sp, ctx):
    """이 후보가 이번 이미지에서 측정 가능한 축인가. degraded면 포즈 의존 축은 불가."""
    return not (ctx["degraded"] and sp in POSE_DEPENDENT)


def _deterministic(ctx):
    """적용가능성 기반 중재(기본 정책).

    리드 우선순위(첫 매칭): 사용자가 말한 적용가능 축 → 측정된 적용가능 축 →
      적용가능한 roadmap focus → 적용가능한 재발 축 → 적용가능 첫 → (전부 비적용이면) 후보 첫.
    핵심: degraded(전신 미검출)면 포즈 의존 축은 '리드'가 못 된다 — 흉상·초상에 전신 비율을
      단정하는 옛 버그를 막는다. 비적용 축은 순서 맨 뒤로(있어도 마지막), 측정·사용자 언급이 앞으로.
    """
    cand = ctx["candidates"]
    obs = ctx["obs_by_sp"]
    appl = [sp for sp in cand if _applicable(sp, ctx)]
    stated = [sp for sp in appl if obs.get(sp, {}).get("from_user")]
    measured = [sp for sp in appl if obs.get(sp, {}).get("measured")]
    recurring = [sp for sp in appl if sp in ctx["recurring"]]
    if stated:
        lead = stated[0]
    elif measured:
        lead = measured[0]
    elif ctx["focus"] in appl:
        lead = ctx["focus"]
    elif recurring:
        lead = recurring[0]
    elif appl:
        lead = appl[0]
    else:
        lead = cand[0]      # 적용 가능한 축이 하나도 없음(전부 degraded 포즈축) → 가설형으로 안내됨

    order = [lead]
    rest = [sp for sp in appl if sp != lead]
    rest.sort(key=lambda sp: (not obs.get(sp, {}).get("measured"),
                              sp not in ctx["recurring"]))   # 측정·재발 먼저(안정 정렬)
    for sp in rest:
        if sp not in order:
            order.append(sp)
    for sp in cand:         # 비적용(degraded 포즈) 축은 맨 뒤
        if sp not in order:
            order.append(sp)
    order = order[:MAX_BLOCKS]
    refs = {sp: (ctx["ref_candidates"].get(sp) or [None])[0] for sp in order}
    emphasis = "progress_first" if (ctx["recurring"] or ctx["steady"]) else "direct"
    return {"order": order, "lead": lead, "refs": refs, "emphasis": emphasis}


def _strip(text):
    t = (text or "").strip()
    if t.startswith("```"):
        inner = t[3:]
        t = inner.split("```", 1)[0] if "```" in inner else inner
        if t.lower().startswith("json"):
            t = t[4:]
    return t.strip()


def _llm_select(ctx, llm):
    """LLM이 후보 중에서 고른다(선택만, 사실 생성 아님). 실패 가능 → 호출부가 검증·폴백한다."""
    items = [{"id": sp,
              "measured": ctx["obs_by_sp"][sp].get("measured", False),
              "recurring": sp in ctx["recurring"],
              "is_focus": sp == ctx["focus"],
              "refs": ctx["ref_candidates"].get(sp, [])}
             for sp in ctx["candidates"]]
    prompt = (
        "너는 그림 코칭 에이전트의 '선택자'다. 아래 후보(이미 측정·진단된 약점들) 중에서만 고른다.\n"
        "규칙: 새 항목이나 새 레퍼런스를 만들지 말 것. 완성도·성장을 판정하지 말 것. 후보 id만 사용할 것.\n"
        f"intent={ctx['intent']}, track={ctx['track']}, roadmap_focus={ctx['focus']}\n"
        f"후보(JSON): {json.dumps(items, ensure_ascii=False)}\n"
        "아래 STRICT JSON만 출력(설명 금지):\n"
        '{"order":[id,...(최대 ' + str(MAX_BLOCKS) + '개)],"lead":id,'
        '"refs":{id:ref_id,...},"emphasis":"progress_first|direct"}\n'
        "order=이번에 보여줄 순서, lead=가장 먼저 다룰 것, refs=각 id에 보여줄 레퍼런스(그 id의 refs 후보 중 하나)."
    )
    return json.loads(_strip(llm.complete_json(prompt)))


def validate(decision, ctx):
    """grounding 강제: 후보 밖 sub_problem/reference는 버린다. 유효 선택이 없으면 None(→폴백)."""
    cand = set(ctx["candidates"])
    order = [sp for sp in (decision.get("order") or []) if sp in cand][:MAX_BLOCKS]
    if not order:
        return None
    refs = {}
    for sp in order:
        rid = (decision.get("refs") or {}).get(sp)
        allowed = ctx["ref_candidates"].get(sp, [])
        refs[sp] = rid if rid in allowed else (allowed[0] if allowed else None)
    lead = decision.get("lead")
    if lead not in order:
        lead = order[0]
    emphasis = decision.get("emphasis")
    if emphasis not in ("progress_first", "direct"):
        emphasis = "direct"
    return {"order": order, "lead": lead, "refs": refs, "emphasis": emphasis}


def decide(diagnosis, refs_by_sp, growth, intent="open", track=None, llm=None):
    """후보 조립 → (LLM 선택 시도 → 검증) → 실패/미사용이면 결정적 정책. 항상 grounded 결과를 보장.

    LLM 선택은 AGENT_LLM_SELECT 환경변수로 옵트인(기본 OFF = 결정적, 추가 비용 0).
    """
    ctx = assemble_context(diagnosis, refs_by_sp, growth, intent, track)
    if not ctx["candidates"]:
        return {"order": [], "lead": None, "refs": {}, "emphasis": "direct"}, ctx
    base = _deterministic(ctx)
    use_llm = llm is not None and os.environ.get("AGENT_LLM_SELECT", "0").lower() in ("1", "true", "yes")
    if use_llm:
        try:
            v = validate(_llm_select(ctx, llm), ctx)
            # LLM 선택도 적용가능성 존중: 리드가 비적용(degraded 포즈축)이면 결정적으로 폴백
            if v and _applicable(v["lead"], ctx):
                return v, ctx
        except Exception as e:
            print(f"[agent] LLM 선택 실패(결정적 폴백): {type(e).__name__}: {e}")
    return base, ctx


def apply(diagnosis, decision):
    """에이전트 선택을 diagnosis에 반영: observations를 선택 순서로 재정렬·필터, primary_focus=lead."""
    if not decision.get("order"):
        return diagnosis
    by_sp = {o["sub_problem"]: o for o in diagnosis.get("observations", [])}
    new_obs = [by_sp[sp] for sp in decision["order"] if sp in by_sp]
    d = dict(diagnosis)
    d["observations"] = new_obs
    d["primary_focus"] = decision["lead"]
    return d


def order_refs(refs_by_sp, decision):
    """선택된 레퍼런스가 각 sub_problem에서 먼저 오도록 안정 재정렬(비파괴; 후보는 그대로 유지)."""
    out = dict(refs_by_sp)
    for sp, rid in (decision.get("refs") or {}).items():
        lst = out.get(sp)
        if lst and rid:
            out[sp] = sorted(lst, key=lambda pair: pair[0] != rid)  # 선택 ref를 앞으로(안정 정렬)
    return out
