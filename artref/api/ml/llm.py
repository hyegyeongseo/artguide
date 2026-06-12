"""LLM 어댑터. provider 미설정 시 DummyLLM(오프라인 템플릿)로 동작.
DummyLLM은 프롬프트에 주입된 <<OBS>>/<<REFS>> 마커를 읽어 근거 있는 GuideResponse JSON을 만든다
→ API 키 없이도 end-to-end가 돌고, 출력은 §20 검증을 통과한다."""
import json, re, requests
from config import settings

_OBS = re.compile(r"<<OBS>>(.*?)<<END>>", re.S)
_REFS = re.compile(r"<<REFS>>(.*?)<<END>>", re.S)


def _default_effect(sub_problem):
    """오프라인/폴백용: taxonomy의 근거 있는 기본 effect (없으면 빈 문자열)."""
    try:
        from pipeline.diagnose import taxonomy
        return taxonomy().get(sub_problem, {}).get("default_effect", "")
    except Exception:
        return ""

class DummyLLM:
    def complete_json(self, prompt: str) -> str:
        mo, mr = _OBS.search(prompt), _REFS.search(prompt)
        if not mo:
            return json.dumps({"mode": "clarify", "message": "무엇을 봐주면 좋을까요?"})
        obs = json.loads(mo.group(1)); refs = json.loads(mr.group(1)) if mr else {}
        blocks = []
        for o in obs.get("observations", []):
            sp = o["sub_problem"]
            sig = (o.get("signal") or "").strip()
            # measured=True + signal 있으면 측정 사실을 관찰로(구체). 아니면 일반 관찰 힌트(단정 X·누출 X).
            observation = (sig if (o.get("measured") and sig) else o["what_to_observe"])
            blocks.append({
                "sub_problem": sp,
                "observation": observation,
                "effect": _default_effect(sp),
                "direction": o["practice_prompt"],
                "reference_ids": (refs.get(sp) or [])[:2],
                "confidence": o["confidence"],
            })
        return json.dumps({
            "mode": "coach", "primary_focus": obs.get("primary_focus"),
            "degraded": obs.get("degraded", False), "blocks": blocks,
            "one_thing": blocks[0]["direction"] if blocks else None,
        }, ensure_ascii=False)

    def stream(self, prompt: str):
        out = self.complete_json(prompt)
        for i in range(0, len(out), 24):
            yield out[i:i + 24]

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_OBJ = re.compile(r"\{.*\}", re.S)

def _extract_json(text: str) -> str:
    """모델 출력에서 GuideResponse JSON만 추출(코드펜스/서두·후미 텍스트 제거)."""
    t = (text or "").strip()
    t = _FENCE.sub("", t).strip()
    if not t.startswith("{"):
        m = _OBJ.search(t)
        if m:
            t = m.group(0)
    return t

XAI_URL = "https://api.x.ai/v1/chat/completions"

class RealLLM:
    """xAI(Grok) 연결. OpenAI 호환 chat/completions. 실패 시 DummyLLM(근거 템플릿)로 폴백."""
    def __init__(self):
        self.key = settings.xai_api_key
        self.model = settings.llm_model or "grok-4.3"
        self._fallback = DummyLLM()

    def complete_json(self, prompt: str) -> str:
        if not self.key:
            return self._fallback.complete_json(prompt)
        try:
            r = requests.post(
                XAI_URL,
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json"},
                json={"model": self.model,
                      "messages": [
                          {"role": "system",
                           "content": "You output only a single valid JSON object. No markdown, no code fences, no prose."},
                          {"role": "user", "content": prompt}],
                      "temperature": 0.3, "max_tokens": 4000},
                timeout=90)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return _extract_json(content)
        except Exception as e:
            print(f"[llm] Grok 호출 실패 → 템플릿 폴백: {type(e).__name__}: {e}")
            return self._fallback.complete_json(prompt)

    def stream(self, prompt: str):
        out = self.complete_json(prompt)
        for i in range(0, len(out), 24):
            yield out[i:i + 24]

def get_llm():
    # 시작 시 어떤 LLM이 활성인지 로그 — 'Grok 붙었나?'를 docker compose logs api 에서 바로 확인.
    if settings.llm_provider:
        llm = RealLLM()
        key_state = "set" if llm.key else "MISSING(.env XAI_API_KEY 비었음 → 템플릿 폴백)"
        print(f"[llm] provider={settings.llm_provider} model={llm.model} key={key_state}")
        return llm
    print("[llm] LLM_PROVIDER 미설정 → DummyLLM(오프라인 템플릿). "
          "Grok 쓰려면 .env에 LLM_PROVIDER=grok 설정 후 컨테이너 재생성하세요.")
    return DummyLLM()
