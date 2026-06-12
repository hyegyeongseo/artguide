"""pipeline/ai_qc.py — 생성형 AI 이미지 적재 직전의 비전 QC/분류 게이트.

이 모듈은 'Gemini(또는 다른 생성기) → 적재' 사이에 끼는 한 단계다. 적재 경로는 지금
선언된 메타데이터(tags.supports 등)를 *그대로 믿는데*, 생성형 이미지는 그 신뢰가 위험하다
(요청한 개념을 안 그렸거나, 해부가 깨졌거나, AI가 약한 축일 수 있다). 그래서 적재 전에
*이미 가진 비전 도구(CLIP·MediaPipe)* 로 생성물을 검사·분류한다. 생성기 자체는 호출하지 않는다
(generator-agnostic — 폴더에 떨어진 이미지가 어디서 왔든 동일하게 검사).

검사 순서(전부 graceful — 도구가 없으면 그 검사만 skip, 앱은 안 깨짐):
  1) 축 적격성(정책·비전 아님) : ai_example 은 명암·구도·빛·색 축에만 의미 있다(AI_AVOID 강제).
                                  요청 축이 전부 부적격이면 즉시 reject.
  2) 일러스트 여부(scene)       : 사진/스크린샷이면 reject(예시 자료는 작품/드로잉이어야).
  3) 개념 일치(CLIP)            : cosine(image, concept) 가 임계 미만이면 reject(요청한 걸 안 그림).
  4) 축 교차검증/자동태깅(CLIP) : 적격 축별 probe(=taxonomy.reference_query)와의 cosine 으로
                                  '실제로 어느 축에 쓸모 있는지'를 비전으로 판단. 선언 축은 검증,
                                  미선언이면 자동 태깅. 검증된 축이 0개면 reject. 결과=supports.
  5) 해부 게이트(pose/hands)    : 인물/손이 있으면 키포인트 정합성을 본다. 기본은 *flag*(자문),
                                  AI_QC_STRICT_ANATOMY=1 이면 깨진 해부를 hard-reject.

반환(verdict) = 순수 dict. ml/ 의존은 전부 *지연/주입* 이라 torch·mediapipe 없이도 import 되고
테스트 가능하다(의존성 주입). 실제 적재는 ai_ingest.qc_and_ingest 가 이 verdict 를 보고 결정한다.
"""
import os
import json

from pipeline.assets import AXIS_PREF, AI_AVOID, AI as _AI_TYPE
from pipeline.diagnose import taxonomy

# ── 적격 축: assets.AXIS_PREF 에서 ai_example(AI) 이 선호에 들어간 축 ∩ not AI_AVOID ──────────
#   현재 정책상 = {value_structure, composition_balance, light_direction, color_harmony}.
#   assets.py 의 정책이 바뀌면 여기도 자동으로 따라간다(하드코딩 아님).
AI_ELIGIBLE_AXES = frozenset(
    sp for sp, pref in AXIS_PREF.items() if _AI_TYPE in pref and sp not in AI_AVOID
)


def _f(env, default):
    try:
        return float(os.environ.get(env, default))
    except Exception:
        return float(default)


# 임계값 — CLIP ViT-B-32(text→image) 코사인은 좋은 매치도 보통 0.20~0.35 라 보수적으로.
#   search.MISS_SCORE_MIN 과 같은 대역. 컬렉션·프롬프트가 자리잡으면 env 로 재튜닝.
def _thresholds(override=None):
    t = {
        "min_artwork": _f("AI_QC_MIN_ARTWORK", 0.45),   # scene: 작품일 확률 하한
        "min_concept": _f("AI_QC_MIN_CONCEPT", 0.22),   # cosine(image, concept) 하한
        "min_axis": _f("AI_QC_MIN_AXIS", 0.20),         # cosine(image, axis_probe) 하한
        "axis_margin": _f("AI_QC_AXIS_MARGIN", 0.0),    # 선언 축 검증 시 추가 여유(엄격도)
        "anatomy_sym_lo": _f("AI_QC_ANAT_SYM_LO", 0.5), # 좌우 사지 길이비 하한(이 밖이면 비대칭 의심)
        "anatomy_sym_hi": _f("AI_QC_ANAT_SYM_HI", 2.0),
    }
    if override:
        t.update({k: float(v) for k, v in override.items() if v is not None})
    return t


def _axis_probe(sp):
    """축 probe 텍스트 = taxonomy 의 reference_query(이미 영어 CLIP 친화 문구). 없으면 축 id."""
    return (taxonomy().get(sp, {}) or {}).get("reference_query") or sp


def _personas_for(axes):
    """검증된 축들 → persona 어휘(taxonomy.personas). 중복 제거, 순서 보존."""
    out, seen = [], set()
    for sp in axes:
        for p in (taxonomy().get(sp, {}) or {}).get("personas", []) or []:
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


# ── 지연 로더(torch/mediapipe 를 import 시점에 끌어오지 않게) ────────────────────────────────
def _real_embedder():
    from ml.embed import embedder
    return embedder


def _real_scene():
    from ml.scene import analyze
    return analyze


def _real_pose():
    from ml.pose import extract
    return extract


def _real_hands():
    from ml.hands import detect
    return detect


def _cos(a, b):
    """두 정규화 벡터의 코사인(=내적). embedder.image/text 는 이미 L2 정규화돼 있음."""
    import numpy as np
    a = np.asarray(a, dtype="float32")
    b = np.asarray(b, dtype="float32")
    return float(np.dot(a, b))


def _anatomy_check(pil, scene, pose_extract, hands_detect, th):
    """인물/손이 있을 때만 키포인트 정합성을 본다. 반환: (ok, flags:list, detail:dict).

    MediaPipe 한계상 'AI 손가락 6개' 같은 미세 오류는 잡지 못한다(항상 21점을 채움). 그래서
    여기서 하는 건 *거친* 무결성 검사다: 좌우 사지 길이비가 극단(비대칭)인지, 포즈가 검출됐는데
    핵심 키포인트 가시성이 바닥인지. 보수적이라 오탐(정상인데 reject)이 적다. 한계는 README 참고.
    """
    flags, detail = [], {}
    person = bool(((scene or {}).get("subject", {}) or {}).get("person", {}).get("present", False))
    detail["person_present"] = person
    if not person:
        return True, flags, detail          # 인물 없음 → 해부 검사 대상 아님(통과)
    try:
        pose = pose_extract(scene, pil)
    except Exception as e:
        detail["pose_error"] = f"{type(e).__name__}: {e}"
        return True, flags, detail          # 도구 없음/실패 → skip(통과, fail-open)
    detail["pose_status"] = pose.get("status")
    if pose.get("status") not in ("ok", "low_confidence") or not pose.get("keypoints"):
        flags.append("pose_undetected_on_figure")   # 인물이라는데 포즈가 안 잡힘 → 형태 모호 의심
        detail["pose_keypoints"] = bool(pose.get("keypoints"))
        return False, flags, detail
    kp = pose["keypoints"]
    try:
        import numpy as np
        def d(i, j):
            return float(np.hypot(kp[i][0] - kp[j][0], kp[i][1] - kp[j][1]))
        # BlazePose: 11/12 어깨, 13/14 팔꿈치, 15/16 손목, 23/24 엉덩이, 25/26 무릎, 27/28 발목
        armL = d(11, 13) + d(13, 15)
        armR = d(12, 14) + d(14, 16)
        legL = d(23, 25) + d(25, 27)
        legR = d(24, 26) + d(26, 28)
        def ratio(a, b):
            return (min(a, b) / max(a, b)) if max(a, b) > 1e-6 else 1.0
        arm_sym = ratio(armL, armR)
        leg_sym = ratio(legL, legR)
        detail["arm_sym"] = round(arm_sym, 3)
        detail["leg_sym"] = round(leg_sym, 3)
        lo = th["anatomy_sym_lo"]
        # 좌우 길이비가 너무 작으면(예: 한쪽이 2배 이상) 비대칭 의심. 단축/회전이면 정상이라 보수적.
        if arm_sym < lo:
            flags.append("arm_length_asymmetry")
        if leg_sym < lo:
            flags.append("leg_length_asymmetry")
    except Exception as e:
        detail["sym_error"] = f"{type(e).__name__}: {e}"
        return True, flags, detail
    # 손 검출은 보조 정보만(가능하면). MediaPipe 가 손가락 수 오류를 직접 못 잡으므로 flag 로만.
    try:
        h = hands_detect(pil)
        detail["hands_available"] = bool(h.get("available"))
        detail["hands_found"] = len(h.get("hands", []))
    except Exception:
        pass
    ok = not flags
    return ok, flags, detail


def qc_example(pil, concept, intended_axes=None, *,
               embedder=None, scene_analyze=None, pose_extract=None, hands_detect=None,
               strict_anatomy=None, thresholds=None, caption=None):
    """생성형 이미지 1장을 검사·분류한다.

    Parameters
    ----------
    pil          : PIL.Image — 검사할 생성 이미지.
    concept      : str — 무엇을 그리려 했는지(영어 권장; CLIP ViT-B-32 는 영어 학습).
    intended_axes: list[str]|None — 의도한 sub_problem 축. None 이면 비전으로 자동 태깅.
    embedder/scene_analyze/pose_extract/hands_detect : 의존성 주입(테스트용). None 이면 실제 ml/ 사용.
    strict_anatomy : bool|None — 깨진 해부를 hard-reject 할지. None 이면 env AI_QC_STRICT_ANATOMY.

    Returns (verdict dict)
    ----------------------
    {accepted, reasons[], supports[], personas[], caption, checks{}, scores{}}
    """
    th = _thresholds(thresholds)
    if strict_anatomy is None:
        strict_anatomy = os.environ.get("AI_QC_STRICT_ANATOMY", "0").lower() in ("1", "true", "yes")
    emb = embedder or _real_embedder()
    scene_fn = scene_analyze or _real_scene()
    pose_fn = pose_extract or _real_pose()
    hands_fn = hands_detect or _real_hands()

    reasons, checks, scores = [], {}, {}

    # ── 1) 축 적격성(정책) ────────────────────────────────────────────────────────────────
    declared = [a for a in (intended_axes or []) if a]
    if declared:
        eligible_declared = [a for a in declared if a in AI_ELIGIBLE_AXES]
        rejected_axes = [a for a in declared if a not in AI_ELIGIBLE_AXES]
        checks["axis_policy"] = {"declared": declared, "eligible": eligible_declared,
                                 "rejected_by_policy": rejected_axes}
        if not eligible_declared:
            reasons.append(
                f"요청 축 {declared} 은 ai_example 부적격(AI_AVOID/형태 축). "
                f"적격 축: {sorted(AI_ELIGIBLE_AXES)}")
            return _verdict(False, reasons, [], caption, concept, checks, scores)
        consider_axes = eligible_declared
    else:
        consider_axes = sorted(AI_ELIGIBLE_AXES)     # 자동 태깅: 적격 축 전체에서 고름
        checks["axis_policy"] = {"declared": [], "auto_tagging": True}

    # ── 이미지 임베딩(한 번) ─────────────────────────────────────────────────────────────
    try:
        iv = emb.image(pil)
    except Exception as e:
        reasons.append(f"이미지 임베딩 실패: {type(e).__name__}: {e}")
        return _verdict(False, reasons, [], caption, concept, checks, scores)

    # ── 2) 일러스트 여부(scene) ──────────────────────────────────────────────────────────
    try:
        scene = scene_fn(pil)
        artwork_p = float(((scene or {}).get("global", {}) or {}).get("confidence", 0.0))
        analyzable = bool((scene or {}).get("analyzable", False))
        scores["artwork_confidence"] = round(artwork_p, 4)
        checks["is_illustration"] = {"analyzable": analyzable, "artwork_confidence": artwork_p}
        # analyzable(작품>0.5) 이 False 거나 작품 신뢰도가 임계 미만이면 사진/스샷으로 보고 reject.
        if (not analyzable) and artwork_p < th["min_artwork"]:
            reasons.append(f"일러스트/작품으로 보이지 않음(작품신뢰도 {artwork_p:.2f}). "
                           "예시 자료는 사진이 아니라 그림이어야 함.")
            return _verdict(False, reasons, [], caption, concept, checks, scores)
    except Exception as e:
        scene = {}
        checks["is_illustration"] = {"skipped": f"{type(e).__name__}: {e}"}

    # ── 3) 개념 일치(CLIP) ───────────────────────────────────────────────────────────────
    try:
        cv = emb.text(concept)
        concept_cos = _cos(iv, cv)
        scores["concept_cos"] = round(concept_cos, 4)
        checks["concept_match"] = {"concept": concept, "cos": concept_cos,
                                   "min": th["min_concept"]}
        if concept_cos < th["min_concept"]:
            reasons.append(f"생성 이미지가 요청 개념과 약하게 일치(cos {concept_cos:.3f} "
                           f"< {th['min_concept']}). 요청한 걸 그리지 않았을 수 있음.")
            return _verdict(False, reasons, [], caption, concept, checks, scores)
    except Exception as e:
        checks["concept_match"] = {"skipped": f"{type(e).__name__}: {e}"}

    # ── 4) 축 교차검증/자동태깅(CLIP) ────────────────────────────────────────────────────
    axis_cos = {}
    for sp in consider_axes:
        try:
            axis_cos[sp] = _cos(iv, emb.text(_axis_probe(sp)))
        except Exception:
            axis_cos[sp] = None
    scores["axis_cos"] = {k: (round(v, 4) if v is not None else None) for k, v in axis_cos.items()}
    verified = [sp for sp in consider_axes
                if axis_cos.get(sp) is not None and axis_cos[sp] >= th["min_axis"] + th["axis_margin"]]
    # 점수 높은 순으로 정렬(가장 잘 맞는 축이 supports 앞)
    verified.sort(key=lambda sp: -(axis_cos.get(sp) or 0.0))
    checks["axis_verify"] = {"considered": consider_axes, "verified": verified,
                             "min": th["min_axis"]}
    if not verified:
        reasons.append("비전 검증에서 어느 적격 축과도 충분히 일치하지 않음 "
                       f"(min {th['min_axis']}). 선언 축과 실제 내용이 불일치하거나 자료성이 약함.")
        return _verdict(False, reasons, [], caption, concept, checks, scores)
    dropped = [a for a in consider_axes if a not in verified]
    if dropped and declared:
        checks["axis_verify"]["dropped_declared"] = [a for a in dropped if a in declared]

    # ── 5) 해부 게이트(pose/hands) ───────────────────────────────────────────────────────
    anat_ok, anat_flags, anat_detail = _anatomy_check(pil, scene, pose_fn, hands_fn, th)
    checks["anatomy"] = {"ok": anat_ok, "flags": anat_flags, "detail": anat_detail,
                         "strict": strict_anatomy}
    if not anat_ok:
        if strict_anatomy:
            reasons.append(f"해부 정합성 의심({anat_flags}) — strict 모드라 적재 거부.")
            return _verdict(False, reasons, verified, caption, concept, checks, scores)
        # 비-strict: reject 하지 않고 flag 만 남긴다(자문). supports 는 light/color/composition 처럼
        # 해부를 '가르치지 않는' 축이므로 형태 결함이 치명적이진 않음.

    cap = caption or _caption_for(verified, concept)
    return _verdict(True, [], verified, cap, concept, checks, scores, anat_flags=anat_flags)


def _caption_for(axes, concept):
    """검증 축 기반 기본 caption(없을 때). 첫 축의 taxonomy 힌트를 가볍게 차용."""
    if not axes:
        return ""
    e = taxonomy().get(axes[0], {}) or {}
    hint = e.get("what_to_observe") or ""
    return hint or "이 부분을 어떻게 보는지 참고할 수 있는 예시예요."


def _verdict(accepted, reasons, supports, caption, concept, checks, scores, anat_flags=None):
    return {
        "accepted": bool(accepted),
        "reasons": reasons,
        "supports": supports,                 # tags.supports 로 들어갈 검증된 축(빈 리스트면 미적재)
        "personas": _personas_for(supports) if supports else [],
        "caption": caption or "",
        "concept": concept,
        "checks": checks,
        "scores": scores,
        "anatomy_flags": anat_flags or [],
    }
