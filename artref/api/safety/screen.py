"""safety/screen.py — 업로드 콘텐츠 모더레이션(기존 no-op 스텁을 대체하는 실제 게이트).

설계 원칙(이 앱의 도메인에 맞춤):
  • 이 제품은 *인물·해부 드로잉* 코칭이다. 예술적 누드/해부 습작은 **정상**이다. 일반적인 NSFW
    필터를 그대로 붙이면 정당한 작품을 오차단한다. 그래서 *대조(contrastive)* 방식으로,
    '명시적 성/하드코어'와 '예술적 인물·해부 습작'을 구분하고, 보수적 임계로 *명백한* 경우만 막는다.
  • 1차선(baseline) = 이미 있는 OpenCLIP 제로샷. 추가 비용 ~0, 모델 의존 없음.
  • 2차선(provider) = 외부 모더레이션 API 훅(MODERATION_PROVIDER). 운영에선 이걸 붙이는 게 정석.
  • 인프라 실패 시 동작은 설정 가능(fail-open 기본 — 앱 안 깨짐 / MODERATION_FAIL_CLOSED=1 로 보수화).

⚠️ 한계(정직하게): CLIP 제로샷은 거친 1차 필터다. 미성년·아동 성착취물(CSAM) 같은 가장 민감한
   범주는 이 휴리스틱으로 신뢰성 있게 못 잡는다 — 운영에선 *전용 모더레이션/해시매칭 제공자*를
   MODERATION_PROVIDER 로 반드시 연결하고, 민감 배포는 fail-closed 를 권장한다.
"""
import os

# 대조 앵커 — '막아야 할 것' vs '정당한 작품/일상'. 후자에 '예술적 인물·해부 습작'을 포함시켜
#   figure drawing 오차단을 줄인다(도메인 특화). 영어(CLIP ViT-B-32 영어 학습).
UNSAFE_ANCHORS = [
    "explicit hardcore pornography",
    "a sexual act, genitalia in a sexual context",
    "graphic violence, gore, blood, or a mutilated body",
]
SAFE_ANCHORS = [
    "an artistic figure drawing or anatomical study",
    "a normal illustration, painting, or sketch",
    "a landscape, still life, or everyday object",
    "an ordinary photo of a clothed person or a scene",
]


def _f(name, default):
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return float(default)


# 임계 — 보수적(명백한 경우만 차단). unsafe 최고점이 safe 최고점보다 MARGIN 이상 높고,
#   동시에 절대값이 MIN 이상일 때만 block. figure study 는 safe 앵커가 받쳐줘 통과한다.
MARGIN = _f("MODERATION_MARGIN", 0.06)
MIN_ABS = _f("MODERATION_MIN", 0.24)


def _fail_open():
    # 기본 fail-open(앱 안 깨짐). 민감 배포는 MODERATION_FAIL_CLOSED=1.
    return os.environ.get("MODERATION_FAIL_CLOSED", "0").lower() not in ("1", "true", "yes")


def _real_embedder():
    from ml.embed import embedder
    return embedder


def _provider():
    """외부 모더레이션 제공자 훅. MODERATION_PROVIDER 가 설정돼 있고 _external_provider 가
    구현돼 있으면 그걸 쓴다. 미설정이면 None(→ baseline)."""
    if not os.environ.get("MODERATION_PROVIDER"):
        return None
    return _external_provider


def _external_provider(pil):
    """운영용 외부 모더레이션 연결 지점(미구현 시 NotImplementedError).
    구현 예: provider SDK 호출 → {'allow': bool, 'reason': str, 'scores': {...}} 반환."""
    raise NotImplementedError(
        "MODERATION_PROVIDER 가 설정됐지만 _external_provider 가 미구현입니다. "
        "여기에 외부 모더레이션 API 호출을 연결하세요.")


def _cos(a, b):
    import numpy as np
    return float(np.dot(np.asarray(a, dtype="float32"), np.asarray(b, dtype="float32")))


def _baseline(pil, embedder):
    """대조 CLIP 제로샷. 반환: {'allow', 'reason', 'scores'}."""
    iv = embedder.image(pil)
    unsafe = {a: _cos(iv, embedder.text(a)) for a in UNSAFE_ANCHORS}
    safe = {a: _cos(iv, embedder.text(a)) for a in SAFE_ANCHORS}
    u_max = max(unsafe.values())
    s_max = max(safe.values())
    block = (u_max >= MIN_ABS) and (u_max - s_max >= MARGIN)
    scores = {"unsafe_max": round(u_max, 4), "safe_max": round(s_max, 4),
              "margin": round(u_max - s_max, 4)}
    if block:
        worst = max(unsafe, key=unsafe.get)
        return {"allow": False, "reason": f"unsafe content suspected ({worst})", "scores": scores}
    return {"allow": True, "reason": None, "scores": scores}


def screen(pil, *, embedder=None, provider=None, fail_open=None):
    """업로드 1장 모더레이션. 반환: {'allow': bool, 'reason': str|None, 'scores': dict}.

    provider 우선(설정 시) → 없으면 CLIP baseline. 인프라 실패 시 fail_open 설정에 따라.
    embedder/provider/fail_open 은 주입 가능(테스트용).
    """
    if fail_open is None:
        fail_open = _fail_open()
    prov = provider if provider is not None else _provider()
    if prov is not None:
        try:
            r = prov(pil)
            r.setdefault("scores", {})
            return r
        except Exception as e:
            print(f"[moderation] provider 실패: {type(e).__name__}: {e}")
            if not fail_open:
                return {"allow": False, "reason": "moderation provider error (fail-closed)",
                        "scores": {}}
            # fail-open: baseline 으로 폴백 시도
    try:
        emb = embedder or _real_embedder()
        return _baseline(pil, emb)
    except Exception as e:
        print(f"[moderation] baseline 실패: {type(e).__name__}: {e}")
        if fail_open:
            return {"allow": True, "reason": None, "scores": {"skipped": True}}
        return {"allow": False, "reason": "moderation unavailable (fail-closed)",
                "scores": {"skipped": True}}
