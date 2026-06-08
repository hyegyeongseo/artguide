from prompts import build_coach_prompt
from safety.validate import coach_with_guardrails

def run_guide(diagnosis, refs_by_sp, retrieved_ids, taxonomy, llm):
    if diagnosis.get("primary_focus") is None:
        from schemas import GuideResponse
        return GuideResponse(mode="clarify", message="무엇을 봐주면 좋을지 알려주세요.")
    prompt = build_coach_prompt(diagnosis, refs_by_sp)
    return coach_with_guardrails(prompt, diagnosis, refs_by_sp,
                                 retrieved_ids, taxonomy, llm)
