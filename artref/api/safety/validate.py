import re
from pydantic import ValidationError
from schemas import GuideResponse, GuideBlock

class Grounding(Exception): pass
class Policy(Exception): pass

FORBIDDEN = re.compile(r"(초보|실력|등급|점수|재능 ?없|잘 그렸|못 그렸|대신 그려|정답 ?이미지)")

def validate_guide(raw_json, diagnosis, retrieved_ids, taxonomy_ids):
    g = GuideResponse.model_validate_json(raw_json)        # 1) 스키마
    if g.mode != "coach":
        return g
    obs = {o["sub_problem"]: o["confidence"] for o in diagnosis["observations"]}
    if g.primary_focus not in taxonomy_ids:
        raise Grounding(f"primary_focus '{g.primary_focus}' not in taxonomy")
    for b in g.blocks:                                     # 2) 닫힌 세계(근거)
        if b.sub_problem not in obs:
            raise Grounding(f"unknown sub_problem '{b.sub_problem}'")
        invented = [r for r in b.reference_ids if r not in retrieved_ids]
        if invented:
            raise Grounding(f"invented refs {invented}")
        if b.confidence > obs[b.sub_problem] + 0.1:
            b.confidence = obs[b.sub_problem]
        if diagnosis["degraded"]:
            b.confidence = min(b.confidence, 0.4)
    text = " ".join([b.observation + b.effect + b.direction for b in g.blocks]
                    + [g.synthesis or "", g.one_thing or "", g.next_steps_note or ""])
    if FORBIDDEN.search(text):                             # 3) 정책 표현
        raise Policy("forbidden phrasing")
    return g

def template_fallback(diagnosis, refs_by_sp, taxonomy):
    blocks = []
    for o in diagnosis["observations"]:
        e = taxonomy[o["sub_problem"]]
        blocks.append(GuideBlock(
            sub_problem=o["sub_problem"], observation=e["what_to_observe"],
            effect=e.get("default_effect", ""), direction=e["practice_prompt"],
            reference_ids=[r for r, _ in refs_by_sp.get(o["sub_problem"], [])][:3],
            confidence=min(o["confidence"], 0.4 if diagnosis["degraded"] else o["confidence"])))
    return GuideResponse(mode="coach", primary_focus=diagnosis["primary_focus"],
                         degraded=diagnosis["degraded"], blocks=blocks,
                         one_thing=(blocks[0].direction if blocks else None))

def _set_refs(g, refs_by_sp):
    """레퍼런스는 검색이 결정한다(LLM은 이미지를 못 보므로 고를 수 없음).
    각 블록을 해당 sub_problem의 검색 상위 3개로 설정 → LLM이 reference_ids를
    빠뜨리거나 일부만 담아도 일관되게 채워진다. 설정값은 retrieved 집합이라 근거 규칙 안전."""
    if g.mode != "coach":
        return g
    for b in g.blocks:
        b.reference_ids = [r for r, _ in refs_by_sp.get(b.sub_problem, [])][:3]
    return g

def coach_with_guardrails(prompt, diagnosis, refs_by_sp, retrieved_ids,
                          taxonomy, llm, max_retries=2):
    tax_ids = set(taxonomy)
    last_err = None
    for _ in range(max_retries + 1):
        raw = llm.complete_json(prompt)
        try:
            g = validate_guide(raw, diagnosis, retrieved_ids, tax_ids)
            return _set_refs(g, refs_by_sp)
        except (ValidationError, Grounding, Policy) as e:
            last_err = e
            prompt += f"\n[수정 필요] {e}. 스키마와 근거(주어진 sub_problem·ref만)를 지켜 다시."
    # 왜 LLM 출력이 거부됐는지 한 줄 남김: Policy=금지표현, Grounding=근거(ref/sub_problem), ValidationError=스키마
    print(f"[guide] 검증 탈락 {max_retries+1}회 → 템플릿 폴백: {type(last_err).__name__}: {last_err}")
    return template_fallback(diagnosis, refs_by_sp, taxonomy)
