from fastapi import FastAPI, UploadFile, Form, Request, HTTPException
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
from pipeline.coach import run_guide
from pipeline.router import resolve, detect_intent
from pipeline.diagnose import diagnose, taxonomy, instrument_version
from pipeline.roadmap import get_roadmap, record_practice, growth_context, _why
from pipeline.growth_stage import apply_cold_start
from pipeline.profiles import resolve_profile
from pipeline import agent
from pipeline.asset_index import build_asset_index
from pipeline.search import search_text, is_miss
from pipeline.mapping import log_miss
from safety.moderation import screen_upload
from ml.upload_guard import UploadRejected
from _security import (valid_ref_id, clean_event, clamp_confidence, cors_origins,
                       PRACTICE_ACTIONS)
from _auth import is_authorized
from _ratelimit import Limiter
from config import settings
from routes_ai_qc import router as ai_qc_router

app = FastAPI(title="창작 지원 AI 에이전트")

# CORS 허용 출처는 env(CORS_ORIGINS)에서 — 배포 도메인을 코드 수정 없이 설정(없으면 로컬 WoZ 기본값).
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ai_qc_router)          # /ai-example/qc · /ai-example/ingest
llm = get_llm()

# ── 접근 통제(인증·레이트리밋) — env 로 opt-in. 둘 다 미설정이면 통과(로컬/WoZ/테스트 그대로) ──
#   API_KEY 설정 시: 보호 경로는 X-API-Key 또는 Bearer 토큰 요구.
#   RATE_LIMIT 설정 시: 키(api-key) 또는 클라이언트 IP 별 한도(+REDIS_URL 있으면 분산 공유).
#   비용이 큰 경로(LLM·CLIP·포즈)와 피드백 쓰기를 보호한다. /healthz·/docs·OPTIONS 는 면제.
_limiter = Limiter(getattr(settings, "rate_limit", ""), getattr(settings, "redis_url", ""))
_EXEMPT_PATHS = ("/healthz", "/docs", "/openapi.json", "/redoc", "/test")


def _client_key(request):
    from _auth import extract_key
    return extract_key(request.headers) or (request.client.host if request.client else "anon")


@app.middleware("http")
async def access_control(request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or any(path.startswith(p) for p in _EXEMPT_PATHS):
        return await call_next(request)
    if not is_authorized(request.headers, getattr(settings, "api_key", "")):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
    allowed, retry = _limiter.allow(_client_key(request))
    if not allowed:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429,
                            headers={"Retry-After": str(retry)})
    return await call_next(request)

@app.on_event("startup")
def _startup():
    try:
        ensure_bucket()
    except Exception:
        pass

@app.get("/healthz")
def healthz():
    return {"ok": True}


# 개발 테스트용 단독 프론트(이미지 업로드 + 한 끗 가이드). 같은 출처라 CORS·API키 없이 동작.
@app.get("/test")
def test_ui():
    import os
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(os.path.dirname(__file__), "test_ui.html"))

def _pipeline(file_bytes, message, user_id="anon", intent="open", track=None, medium=None):
    try:
        pil = normalize(BytesIO(file_bytes))   # 디코드 전 바이트/픽셀/포맷 한도 강제(upload_guard)
    except UploadRejected as e:
        return None, {"mode": "refused",
                      "message": "이 이미지는 처리할 수 없어요(크기·형식 제한). 다른 이미지를 올려주세요.",
                      "reason": str(e)}
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
    # 그림 단계(완성작/연습): 폼 입력 우선, 없으면 메시지 키워드. 압축 이력(growth)을 진단 랭킹에 흘린다.
    intent = detect_intent(message, explicit=intent)
    # track 프로파일: 명시 track 우선, 없으면 scene(인물 유무)로 자동. 진단 게이팅·norm과 로드맵 커리큘럼에 동시 적용.
    profile = resolve_profile(track, scene)
    growth = growth_context(user_id, track=track, curriculum=profile["curriculum"],
                            degraded=(pose.get("status") != "ok"), llm=llm)
    dx = diagnose(scene, pose, pil, personas, user_terms, growth=growth, profile=profile)
    # 콜드스타트(첫 업로드·이력 없음): 로드맵 진입 집중 축을 '그림에서 측정된 약점'으로 교정한다.
    #   업로드 = 진단 + 성장 경로 설정 트리거(멘토링). 이력이 쌓이면 apply_cold_start 는 아무것도 안 바꾼다.
    measured = [o["sub_problem"] for o in dx["observations"] if o.get("measured")]
    growth = apply_cold_start(growth, measured, profile["curriculum"], why_fn=_why)
    tax = taxonomy()
    refs_by_sp, retrieved = {}, set()
    for o in dx["observations"]:
        sp = o["sub_problem"]
        persona_hint = tax[sp]["personas"][0]
        # 손 문제엔 손 크롭(region=hand) 우선. 없으면 필터 없이 폴백.
        f = {"region": "hand"} if sp == "hand_structure" else None
        # delta4: medium/track 전달 → 같은 매체·트랙 ai_example 에 soft boost(MEDIUM/TRACK_BOOST).
        hits = search_text(o["reference_query"], persona_hint, filters=f, sub_problem=sp,
                           track=track, medium=medium)
        if not hits and f:
            hits = search_text(o["reference_query"], persona_hint, sub_problem=sp,
                               track=track, medium=medium)
        # miss(빈 결과/낮은 점수) → 라이브러리 보강 큐로. 측정된 관찰일수록 가치 큰 miss.
        if is_miss(hits):
            log_miss(o["reference_query"],
                     context={"sub_problem": sp, "persona": persona_hint,
                              "measured": o.get("measured", False),
                              "region": "hand" if sp == "hand_structure" else None,
                              "top_score": round(float(hits[0][1]), 4) if hits else None})
        refs_by_sp[sp] = [(rid, "") for rid, _ in hits]
        retrieved |= {rid for rid, _ in hits}
    return (dx, refs_by_sp, retrieved, tax, growth, intent), None

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


def _log_observable(user_id, measurable, guide_id):
    """이번 업로드에서 *측정 가능*했던 축(주제 등장)을 'observable'로 누적 — flagged('seen')과 분리 기록.
    roadmap 이 '부재(안 그림) → steady'를 '개선(그렸는데 덜 걸림)'과 구분하게 하는 관측층 신호.
    실패해도 /guide 는 정상 응답."""
    rows = [dict(u=user_id or "anon", sp=sp, g=guide_id, iv=instrument_version())
            for sp in (measurable or ())]
    if not rows:
        return
    try:
        with engine.begin() as cx:
            cx.execute(text("INSERT INTO practice_log (user_id, sub_problem, action, guide_id, instrument_version) "
                            "VALUES (:u, :sp, 'observable', :g, :iv)"), rows)
    except Exception as e:
        print(f"[guide] observable 로깅 실패(무시): {type(e).__name__}: {e}")


@app.post("/guide")
async def guide_ep(file: UploadFile, message: str = Form(""),
                   user_id: str = Form("anon"), intent: str = Form("open"),
                   track: str = Form(None), medium: str = Form(None)):
    ctx, early = _pipeline(await file.read(), message, user_id, intent, track, medium)
    if early:
        return early
    dx, refs_by_sp, retrieved, tax, growth, intent = ctx
    # 에이전트 선택층(grounded): 룰이 낸 후보 중에서 무엇을 먼저·어떤 레퍼런스로 보여줄지 *선택* → 검증 → 적용.
    decision, _ = agent.decide(dx, refs_by_sp, growth, intent=intent, track=track, llm=llm)
    dx = agent.apply(dx, decision)
    refs_by_sp = agent.order_refs(refs_by_sp, decision)
    # 3D 백본(self_render) → guide_asset backbone_3d 다리. 보여줄 축 + 로드맵 집중/다음 축에 대해 후보를 모은다.
    #   적재된 self_render 가 없으면 빈 색인 → assets 가 svg 도식 바닥으로 폴백(슬롯은 안 빔).
    asset_sps = [o["sub_problem"] for o in dx.get("observations", [])]
    if growth:
        asset_sps += [growth.get("current_focus"), growth.get("next_goal")]
    asset_index = build_asset_index(asset_sps)
    resp = run_guide(dx, refs_by_sp, retrieved, tax, llm, growth=growth, intent=intent,
                     asset_index=asset_index)
    if resp.mode == "coach":
        resp.guide_id = str(uuid.uuid4())
        _log_impressions(resp.guide_id, refs_by_sp, tax)
        # 사용자에게 '실제로 보여준' 블록만 'seen'으로 누적 → "자주 막히는 부분"이 보여준 것 기준으로
        # 정직해진다(진단됐지만 LLM이 뺀 약한 추정·persona 기본값은 recurring을 오염시키지 않음).
        for b in resp.blocks:
            record_practice(user_id, b.sub_problem, "seen",
                            confidence=b.confidence, guide_id=resp.guide_id)
        _log_observable(user_id, dx.get("measurable", ()), resp.guide_id)
    return resp.model_dump()

@app.post("/guide/stream")
async def guide_stream_ep(file: UploadFile, message: str = Form(""),
                          user_id: str = Form("anon"), intent: str = Form("open"),
                          track: str = Form(None), medium: str = Form(None)):
    ctx, early = _pipeline(await file.read(), message, user_id, intent, track, medium)
    if early:
        body = [f"data: {json.dumps(early, ensure_ascii=False)}\n\n", "data: [DONE]\n\n"]
        return StreamingResponse(iter(body), media_type="text/event-stream")
    dx, refs_by_sp, retrieved, tax, growth, intent = ctx
    decision, _ = agent.decide(dx, refs_by_sp, growth, intent=intent, track=track, llm=llm)
    dx = agent.apply(dx, decision)
    refs_by_sp = agent.order_refs(refs_by_sp, decision)
    # 가드레일 통과 응답을 *먼저* 만들고(닫힌세계·금지표현·근거 검증), 그 검증된 블록만 스트리밍한다.
    #   이전엔 raw LLM 토큰을 그대로 흘려 /guide/stream 만 가드레일을 우회했다(평가어·환각 ref 누출 위험).
    #   이제 두 경로(/guide·/guide/stream)가 같은 검증을 거친다 — 핵심 안전 불변식 유지.
    asset_sps = [o["sub_problem"] for o in dx.get("observations", [])]
    if growth:
        asset_sps += [growth.get("current_focus"), growth.get("next_goal")]
    asset_index = build_asset_index(asset_sps)
    resp = run_guide(dx, refs_by_sp, retrieved, tax, llm, growth=growth, intent=intent,
                     asset_index=asset_index)
    if resp.mode == "coach":
        resp.guide_id = str(uuid.uuid4())
        _log_impressions(resp.guide_id, refs_by_sp, tax)
        for b in resp.blocks:
            record_practice(user_id, b.sub_problem, "seen",
                            confidence=b.confidence, guide_id=resp.guide_id)
        _log_observable(user_id, dx.get("measurable", ()), resp.guide_id)

    def gen():
        payload = resp.model_dump()
        # 점진 렌더용: 블록을 하나씩 흘린 뒤, 마지막에 전체 응답(메타·next_steps 포함)을 보낸다.
        for b in payload.get("blocks", []):
            yield f"data: {json.dumps({'type': 'block', 'block': b}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'guide': payload}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/image/{ref_id}")
def image(ref_id: str):
    """ref_id → 실제 이미지로 302 리다이렉트(임시 presigned URL).
    운영자가 /search 결과의 url을 그대로 테스트 페이지에 붙여넣을 수 있게 해주는 연결고리."""
    if not valid_ref_id(ref_id):
        raise HTTPException(status_code=404, detail="invalid ref_id")
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

_adopt_schema_ready = False
def _ensure_adopt_schema():
    """adoption_log.event ENUM에 'disliked' 슬롯을 1회 확장(마이그레이션 없이 dev 편의)."""
    global _adopt_schema_ready
    if _adopt_schema_ready:
        return
    try:
        with engine.begin() as cx:
            cx.execute(text("ALTER TABLE adoption_log MODIFY event "
                            "ENUM('shown','clicked','saved','liked','disliked') NOT NULL"))
        _adopt_schema_ready = True
    except Exception as e:
        print(f"[adopt] event ENUM 확장 실패(무시): {type(e).__name__}: {e}")


@app.post("/adopt")
def adopt(e: AdoptEvent):
    _ensure_adopt_schema()
    if clean_event(e.event) is None:          # 화이트리스트 밖 이벤트 차단(랭커 오염 방지)
        raise HTTPException(status_code=400, detail="invalid event")
    with engine.begin() as cx:
        cx.execute(text("""INSERT INTO adoption_log
          (guide_id,reference_id,persona,source_type,event)
          VALUES (:guide_id,:reference_id,:persona,:source_type,:event)"""), e.model_dump())
    return {"ok": True}


# ── 진척(성장) 레이어 라우트 — /roadmap · /practice ──────────────────────────
class PracticeEvent(BaseModel):
    user_id: str = "anon"
    sub_problem: str
    action: str            # 'tried' | 'later' (UI의 시도해봤어요/나중에)
    confidence: float | None = None
    guide_id: str | None = None


@app.get("/roadmap")
def roadmap_ep(user_id: str = "anon", track: str = None):
    """현재 단계 → 다음 연습 → 다음 목표 + 자주 막히는 부분(recurring). track 커리큘럼 기준."""
    return get_roadmap(user_id, track=track)


@app.post("/practice")
def practice_ep(e: PracticeEvent):
    if clean_event(e.action, PRACTICE_ACTIONS) is None:   # 'tried'|'later'|'seen' 만 허용
        raise HTTPException(status_code=400, detail="invalid action")
    record_practice(e.user_id, e.sub_problem, e.action,
                    clamp_confidence(e.confidence), e.guide_id)
    return {"ok": True}


@app.get("/svg/{ref_id}")
def svg(ref_id: str):
    """구축선 SVG 서빙 (/image 의 SVG 버전). svg_key 없으면 조용히 빈 응답."""
    if not valid_ref_id(ref_id):
        raise HTTPException(status_code=404, detail="invalid ref_id")
    try:
        with engine.begin() as cx:
            row = cx.execute(
                text("SELECT svg_key FROM reference_images WHERE ref_id=:r"),
                {"r": ref_id},
            ).fetchone()
        if not row or not row[0]:
            return {"error": "no svg for this ref"}
        return RedirectResponse(presigned_url(row[0]))
    except Exception as e:
        print(f"[svg] 조회 실패(무시): {type(e).__name__}: {e}")
        return {"error": "svg lookup failed"}


@app.get("/guide-asset/{ref_id:path}")
def guide_asset(ref_id: str):
    """설명 자료 슬롯 서빙. 'floor:<축>'이면 도식 SVG를 인라인으로(적재 0개여도 항상 나옴),
    'reference/<name>.svg'면 파일 기반 구축 도식을 인라인으로(경로탈출 차단),
    그 외(적재된 ai_example·backbone_3d)는 reference_images.image_key 로 presigned 리다이렉트."""
    from pipeline.assets import floor_svg
    from pipeline.asset_index import read_reference_svg
    from fastapi.responses import Response
    if ref_id.startswith("floor:"):
        sp = ref_id.split(":", 1)[1]
        return Response(content=floor_svg(sp), media_type="image/svg+xml")
    if ref_id.startswith("reference/"):
        svg = read_reference_svg(ref_id)
        if svg:
            return Response(content=svg, media_type="image/svg+xml")
        # 파일 못 찾아도 깨진 이미지 대신 빈 SVG(슬롯 신뢰 유지). 로그만 남김.
        print(f"[guide-asset] reference 파일 없음(빈 SVG 폴백): {ref_id}")
        return Response(content='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 180"/>',
                        media_type="image/svg+xml")
    if not valid_ref_id(ref_id):
        raise HTTPException(status_code=404, detail="invalid ref_id")
    try:
        with engine.begin() as cx:
            row = cx.execute(
                text("SELECT image_key FROM reference_images WHERE ref_id=:r"),
                {"r": ref_id},
            ).fetchone()
        if not row or not row[0]:
            return {"error": "no asset for this ref"}
        return RedirectResponse(presigned_url(row[0]))
    except Exception as e:
        print(f"[guide-asset] 조회 실패(무시): {type(e).__name__}: {e}")
        return {"error": "asset lookup failed"}
