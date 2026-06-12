"""routes_ai_qc.py — 생성형 이미지 QC/적재 라우트(추가형 APIRouter).

main.py 를 덮어쓰지 않도록 별도 라우터로 분리했다. main.py 에 두 줄만 추가하면 붙는다:

    from routes_ai_qc import router as ai_qc_router      # 다른 import 들과 함께
    app.include_router(ai_qc_router)                     # app 생성 뒤 아무 곳

엔드포인트:
  POST /ai-example/qc      — 드라이런. 적재하지 않고 verdict(통과여부·사유·검증축·점수)만 반환.
  POST /ai-example/ingest  — QC 통과 시에만 ai_example 로 적재하고 ref_id 반환.

multipart 폼:
  file     : 생성된 이미지(png/jpg/webp)
  concept  : 무엇을 그리려 했는지(영어 권장 — CLIP ViT-B-32 는 영어 학습)
  axes     : 의도 축, 콤마구분(예: "light_direction,color_harmony"). 비우면 비전 자동 태깅.
  caption  : (선택) 사용자 노출 캡션. 비우면 코드가 축 기반으로 채움.
  strict_anatomy : (선택, ingest) "1"이면 깨진 해부 hard-reject.
"""
from fastapi import APIRouter, UploadFile, Form, HTTPException
from io import BytesIO

from ml.normalize import normalize
from pipeline.ai_qc import qc_example
from pipeline.ai_ingest import qc_and_ingest, MEDIUMS
from pipeline.profiles import PROFILES

router = APIRouter(tags=["ai-example"])


def _axes(s):
    return [a.strip() for a in (s or "").split(",") if a.strip()] or None


def _clean(s):
    return (s or "").strip() or None


@router.post("/ai-example/qc")
async def ai_example_qc(file: UploadFile, concept: str = Form(...),
                        axes: str = Form(""), caption: str = Form(None),
                        strict_anatomy: str = Form("0")):
    pil = normalize(BytesIO(await file.read()))
    v = qc_example(pil, concept, _axes(axes), caption=caption,
                   strict_anatomy=strict_anatomy.lower() in ("1", "true", "yes"))
    return v


@router.post("/ai-example/ingest")
async def ai_example_ingest(file: UploadFile, concept: str = Form(...),
                            axes: str = Form(""), caption: str = Form(None),
                            license: str = Form("CC0"),
                            attribution: str = Form("AI-generated example (QC-gated)"),
                            medium: str = Form(None), track: str = Form(None),
                            strict_anatomy: str = Form("0")):
    medium, track = _clean(medium), _clean(track)
    # 취향 매칭 신호(soft boost) — 오타로 죽은 부스트가 되지 않게 어휘를 검증한다.
    if medium and medium not in MEDIUMS:
        raise HTTPException(422, f"medium must be one of {sorted(MEDIUMS)}")
    if track and track not in PROFILES:
        raise HTTPException(422, f"track must be one of {sorted(PROFILES)}")
    pil = normalize(BytesIO(await file.read()))
    res = qc_and_ingest(pil, concept, _axes(axes), license=license,
                        attribution=attribution, caption=caption,
                        medium=medium, track=track,
                        strict_anatomy=strict_anatomy.lower() in ("1", "true", "yes"))
    # 적재 실패(QC 탈락)면 사유를 그대로 노출 — 운영자가 프롬프트/축을 고치게.
    return res
