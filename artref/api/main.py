from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from io import BytesIO
import json
import uuid
from sqlalchemy import text, bindparam

from stores.db import engine
from stores.s3 import ensure_bucket, presigned_url
from ml.normalize import normalize
from ml.scene import analyze
from ml.pose import extract
from ml.llm import get_llm
from ml.guide import run_guide
from prompts import build_coach_prompt
from pipeline.router import resolve
from pipeline.diagnose import diagnose, taxonomy
from pipeline.search import search_text, is_miss
from pipeline.mapping import log_miss
from safety.moderation import screen_upload

app = FastAPI(title="창작 지원 AI 에이전트")

# 운영자 WoZ 테스트 페이지(localhost:5173)에서의 자동 채우기/조회 대비.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
llm = get_llm()

@app.on_event("startup")
def _startup():
    try:
        ensure_bucket()
    except Exception:
        pass

@app.get("/healthz")
def healthz():
    return {"ok": True}

def _pipeline(file_bytes, message):
    pil = normalize(BytesIO(file_bytes))
    if not screen_upload(pil)["allow"]:
        return None, {"mode": "refused", "message": "이 업로드는 처리할 수 없어요. 작품 이미지를 올려주세요."}
    scene = analyze(pil)
    pose = extract(scene, pil)
    mode, personas, user_terms = resolve(message, scene)
    if mode == "redirect":
        return None, {"mode": "redirect",
                      "message": "직접 그려드리진 않지만, 보고 싶은 부분을 알려주면 그 지점과 레퍼런스로 같이 봐줄게요."}
    if mode == "clarify":
        return None, {"mode": "clarify", "message": "분석할 그림인지, 어떤 점을 봐주면 좋을지 알려주세요."}
    dx = diagnose(scene, pose, pil, personas, user_terms)
    tax = taxonomy()
    refs_by_sp, retrieved = {}, set()
    for o in dx["observations"]:
        sp = o["sub_problem"]
        persona_hint = tax[sp]["personas"][0]
        # 손 문제엔 손 크롭(region=hand) 우선. 없으면 필터 없이 폴백.
        f = {"region": "hand"} if sp == "hand_structure" else None
        hits = search_text(o["reference_query"], persona_hint, filters=f, sub_problem=sp)
        if not hits and f:
            hits = search_text(o["reference_query"], persona_hint, sub_problem=sp)
        # miss(빈 결과/낮은 점수) → 라이브러리 보강 큐로. 측정된 관찰일수록 가치 큰 miss.
        if is_miss(hits):
            log_miss(o["reference_query"],
                     context={"sub_problem": sp, "persona": persona_hint,
                              "measured": o.get("measured", False),
                              "region": "hand" if sp == "hand_structure" else None,
                              "top_score": round(float(hits[0][1]), 4) if hits else None})
        refs_by_sp[sp] = [(rid, "") for rid, _ in hits]
        retrieved |= {rid for rid, _ in hits}
    return (dx, refs_by_sp, retrieved, tax), None

@app.post("/analyze")
async def analyze_ep(file: UploadFile, message: str = Form("")):
    ctx, early = _pipeline(await file.read(), message)
    if early:
        return early
    dx = ctx[0]
    return {"primary_focus": dx["primary_focus"], "degraded": dx["degraded"], "persona": dx["persona"],
            "observations": [{"sub_problem": o["sub_problem"], "confidence": o["confidence"],
                              "signal": o["signal"]} for o in dx["observations"]]}

def _log_impressions(guide_id, refs_by_sp, tax):
    """노출(shown)을 sub_problem·persona·source_type와 함께 서버에서 기록(피드백 신호 원천).
    클라가 보내던 'shown'은 서버가 더 완전하게 대체. 실패해도 /guide는 정상 응답."""
    ref_ids = list({rid for refs in refs_by_sp.values() for rid, _ in refs})
    if not ref_ids:
        return
    try:
        with engine.begin() as cx:
            src = {}
            q = text("SELECT ref_id, source_type FROM reference_images WHERE ref_id IN :ids") \
                .bindparams(bindparam("ids", expanding=True))
            for ref_id, st in cx.execute(q, {"ids": ref_ids}):
                src[ref_id] = st
            rows = []
            for sp, refs in refs_by_sp.items():
                persona = tax[sp]["personas"][0]
                for rid, _ in refs:
                    rows.append(dict(g=guide_id, r=rid, p=persona,
                                     st=src.get(rid, "unknown"), sp=sp))
            if rows:
                cx.execute(text("""INSERT INTO adoption_log
                    (guide_id,reference_id,persona,source_type,sub_problem,event)
                    VALUES (:g,:r,:p,:st,:sp,'shown')"""), rows)
    except Exception as e:
        print(f"[guide] 노출 로깅 실패(무시): {type(e).__name__}: {e}")


@app.post("/guide")
async def guide_ep(file: UploadFile, message: str = Form("")):
    ctx, early = _pipeline(await file.read(), message)
    if early:
        return early
    dx, refs_by_sp, retrieved, tax = ctx
    resp = run_guide(dx, refs_by_sp, retrieved, tax, llm)
    if resp.mode == "coach":
        resp.guide_id = str(uuid.uuid4())
        _log_impressions(resp.guide_id, refs_by_sp, tax)
    return resp.model_dump()

@app.post("/guide/stream")
async def guide_stream_ep(file: UploadFile, message: str = Form("")):
    ctx, early = _pipeline(await file.read(), message)
    if early:
        body = [f"data: {json.dumps(early, ensure_ascii=False)}\n\n", "data: [DONE]\n\n"]
        return StreamingResponse(iter(body), media_type="text/event-stream")
    dx, refs_by_sp, retrieved, tax = ctx
    prompt = build_coach_prompt(dx, refs_by_sp)

    def gen():
        for tok in llm.stream(prompt):
            yield f"data: {tok}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/image/{ref_id}")
def image(ref_id: str):
    """ref_id → 실제 이미지로 302 리다이렉트(임시 presigned URL).
    운영자가 /search 결과의 url을 그대로 테스트 페이지에 붙여넣을 수 있게 해주는 연결고리."""
    with engine.begin() as cx:
        row = cx.execute(
            text("SELECT image_key FROM reference_images WHERE ref_id=:r"),
            {"r": ref_id},
        ).fetchone()
    key = row[0] if row else f"images/{ref_id}.png"
    return RedirectResponse(presigned_url(key))


@app.post("/search")
def search_ep(request: Request, query: str = Form(...), persona: str = Form(None),
              gender: str = Form(None), body_type: str = Form(None),
              region: str = Form(None), category: str = Form(None)):
    base = str(request.base_url).rstrip("/")
    filters = {"gender": gender, "body_type": body_type,
               "region": region, "category": category}
    hits = search_text(query, persona, filters=filters)
    # 붙여넣기 가능한 절대 URL 동봉 → 운영자가 /docs에서 바로 복사.
    return {"hits": [{"ref_id": rid, "score": round(float(s), 4),
                      "url": f"{base}/image/{rid}"} for rid, s in hits]}

class AdoptEvent(BaseModel):
    guide_id: str
    reference_id: str
    persona: str
    source_type: str
    event: str

@app.post("/adopt")
def adopt(e: AdoptEvent):
    with engine.begin() as cx:
        cx.execute(text("""INSERT INTO adoption_log
          (guide_id,reference_id,persona,source_type,event)
          VALUES (:guide_id,:reference_id,:persona,:source_type,:event)"""), e.model_dump())
    return {"ok": True}
