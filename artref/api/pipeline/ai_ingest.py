"""pipeline/ai_ingest.py — QC 게이트를 통과한 생성형 이미지만 기존 ingest() 로 적재.

흐름:  pil + concept(+축)  →  ai_qc.qc_example  →  통과면 pipeline.ingest.ingest(source_type='ai_example')
                                                  →  실패면 적재 안 함 + 사유 반환.

검증된 supports/personas/caption 을 tags 로 묶어 넣으므로, asset_index._ai_candidates_from_rows 가
읽는 tags.supports 가 *비전으로 검증된 축* 이 된다(선언 신뢰 → 검증 신뢰로 전환). AI_AVOID 축은
qc 단계에서 이미 떨어져 들어올 수 없다.

모든 부수효과(audit 로깅)는 best-effort — 실패해도 적재/응답은 정상. DB 테이블(005 마이그레이션)이
없으면 JSONL 파일로 폴백한다(AI_QC_AUDIT_LOG, 기본 /tmp/ai_qc_audit.jsonl).
"""
import os
import json
import datetime


def _audit(record):
    """QC 결과 1건 기록. ai_qc_audit 테이블 있으면 거기, 없으면 JSONL. 전부 예외 삼킴."""
    try:
        from stores.db import engine
        from sqlalchemy import text
        with engine.begin() as cx:
            cx.execute(text(
                "INSERT INTO ai_qc_audit "
                "(ref_id, accepted, concept, intended_axes, supports, reasons, scores) "
                "VALUES (:r,:a,:c,:ia,:s,:rs,:sc)"),
                dict(r=record.get("ref_id"), a=1 if record.get("accepted") else 0,
                     c=(record.get("concept") or "")[:512],
                     ia=json.dumps(record.get("intended_axes")),
                     s=json.dumps(record.get("supports")),
                     rs=json.dumps(record.get("reasons")),
                     sc=json.dumps(record.get("scores"))))
        return
    except Exception as e:
        # 테이블 없음/DB 없음 → 파일 폴백
        if os.environ.get("AI_QC_DEBUG"):
            print(f"[ai_qc] DB audit 실패 → 파일 폴백: {type(e).__name__}: {e}")
    try:
        path = os.environ.get("AI_QC_AUDIT_LOG", "/tmp/ai_qc_audit.jsonl")
        record = dict(record)
        record["ts"] = datetime.datetime.utcnow().isoformat() + "Z"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[ai_qc] audit 로깅 실패(무시): {type(e).__name__}: {e}")


MEDIUMS = frozenset({"digital", "pencil", "watercolor", "sketch", "painting"})


def qc_and_ingest(pil, concept, intended_axes=None, *,
                  license="CC0", attribution="AI-generated example (QC-gated)",
                  commercial_ok=True, extra_tags=None, audit=True,
                  medium=None, track=None,
                  ingest_fn=None, qc_fn=None, **qc_kwargs):
    """QC 통과 시에만 적재. 반환: {accepted, ref_id|None, verdict}.

    ingest_fn/qc_fn 은 테스트용 주입구. 기본은 실제 pipeline.ingest.ingest / ai_qc.qc_example.
    extra_tags 는 tags 에 병합(예: {'style':'cel','prompt_id':...}). supports/caption/qc 는 코드가 채움.
    medium/track 은 취향 매칭 신호 — payload_extra(Qdrant)로 보내야 search 의 boost 가 읽고(MEDIUM/TRACK_BOOST),
    tags(MySQL)에도 남겨 재임베딩/재구축 때 보존한다(역할이 다름: payload_extra=조회, tags=durability).
    """
    qc = qc_fn or _real_qc()
    verdict = qc(pil, concept, intended_axes, **qc_kwargs)

    if not verdict.get("accepted"):
        if audit:
            _audit({"ref_id": None, "accepted": False, "concept": concept,
                    "intended_axes": intended_axes, "supports": verdict.get("supports"),
                    "reasons": verdict.get("reasons"), "scores": verdict.get("scores")})
        return {"accepted": False, "ref_id": None, "verdict": verdict}

    ingest = ingest_fn or _real_ingest()
    supports = verdict["supports"]
    tags = {"supports": supports, "caption": verdict.get("caption", ""),
            "concept": concept, "qc": verdict.get("scores", {})}
    if verdict.get("anatomy_flags"):
        tags["anatomy_flags"] = verdict["anatomy_flags"]
    if medium:
        tags["medium"] = medium          # MySQL 기록(durability — 재구축 시 보존)
    if track:
        tags["track"] = track
    if extra_tags:
        tags.update(extra_tags)

    payload_extra = {"category": "ai_example"}
    if medium:
        payload_extra["medium"] = medium  # Qdrant payload → search boost 가 읽는 신호
    if track:
        payload_extra["track"] = track

    ref_id = ingest(
        pil,
        source_type="ai_example",
        license=license,
        personas=verdict.get("personas", []),
        tags=tags,
        attribution=attribution,
        commercial_ok=commercial_ok,
        payload_extra=payload_extra,
    )
    if audit:
        _audit({"ref_id": ref_id, "accepted": True, "concept": concept,
                "intended_axes": intended_axes, "supports": supports,
                "reasons": [], "scores": verdict.get("scores")})
    return {"accepted": True, "ref_id": ref_id, "verdict": verdict}


def _real_qc():
    from pipeline.ai_qc import qc_example
    return qc_example


def _real_ingest():
    from pipeline.ingest import ingest
    return ingest
