"""ai_qc 게이트 테스트 — torch·mediapipe·DB 없이 순수 로직만 검증(의존성 주입).

확인하는 안전 속성:
  1) AI_AVOID/형태 축은 정책 단계에서 즉시 거부(비전 보기도 전에).
  2) 개념 일치(cos) 임계 미만이면 거부.
  3) 적격 축 + 개념 통과 + probe 일치 → 통과하고 supports/personas 가 검증 축으로 채워짐.
  4) 미선언이면 비전으로 자동 태깅(가장 잘 맞는 적격 축).
  5) 선언했지만 검증 안 된 축은 supports 에서 떨어짐(통과는 유지).
  6) 어떤 적격 축과도 안 맞으면 거부.
  7) 사진/스샷(analyzable=False, 작품신뢰도 낮음)이면 거부.
  8) 인물 해부 비대칭: strict 면 거부, 기본은 통과+flag.
  9) qc_and_ingest: 통과분만 source_type='ai_example' + tags.supports(검증축)로 적재.

실행:  artref/api 에서  python -m tests.test_ai_qc   (또는 pytest 아닌 직접 실행)
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from pipeline.diagnose import taxonomy
from pipeline import ai_qc, ai_ingest

# 적격 축 probe 텍스트(= taxonomy.reference_query). 테스트에서 image_cos 스펙에 쓴다.
RQ = {sp: taxonomy()[sp]["reference_query"]
      for sp in ("value_structure", "composition_balance", "light_direction", "color_harmony")}


class FakeEmbedder:
    """image()·text() 가 미리 정한 코사인을 그대로 내도록 만든 가짜 임베더.

    image_cos = {라벨문자열: 코사인}. text(라벨)=one-hot, image()=각 라벨 dim 에 코사인을 채운 벡터.
    => _cos(image, text(라벨)) == image_cos[라벨]. 등록 안 된 라벨은 코사인 0.
    """
    def __init__(self, image_cos):
        self.labels = list(image_cos.keys())
        self.idx = {lab: i for i, lab in enumerate(self.labels)}
        self.N = max(8, len(self.labels))
        self._img = np.zeros(self.N, dtype="float32")
        for lab, c in image_cos.items():
            self._img[self.idx[lab]] = float(c)
        self.model_id = "fake"

    def image(self, pil):
        return self._img.copy()

    def text(self, s):
        v = np.zeros(self.N, dtype="float32")
        if s in self.idx:
            v[self.idx[s]] = 1.0
        return v


def scene_ok(person=False, analyzable=True, conf=0.7):
    def _fn(pil):
        return {"analyzable": analyzable, "global": {"confidence": conf},
                "subject": {"person": {"present": person, "prominence": 0.9 if person else 0.1}}}
    return _fn


def pose_none(scene, pil):
    return {"status": "skipped", "reason": "no_person_detected"}


def hands_none(pil):
    return {"available": False, "hands": []}


def _kp_asymmetric():
    """좌우 팔 길이비가 극단인 33키포인트(팔 비대칭 flag 유발). 나머지는 대칭/무난."""
    kp = [(0.0, 0.0, 1.0)] * 33
    # 어깨 11/12, 팔꿈치 13/14, 손목 15/16
    kp[11] = (0.0, 0.0, 1.0); kp[13] = (0.0, 1.0, 1.0); kp[15] = (0.0, 3.0, 1.0)   # 왼팔 길게
    kp[12] = (1.0, 0.0, 1.0); kp[14] = (1.0, 0.1, 1.0); kp[16] = (1.0, 0.2, 1.0)   # 오른팔 짧게
    # 다리 23/24,25/26,27/28 대칭
    kp[23] = (0.0, 4.0, 1.0); kp[25] = (0.0, 5.0, 1.0); kp[27] = (0.0, 6.0, 1.0)
    kp[24] = (1.0, 4.0, 1.0); kp[26] = (1.0, 5.0, 1.0); kp[28] = (1.0, 6.0, 1.0)
    return kp


def pose_asymmetric(scene, pil):
    return {"status": "ok", "mean_visibility": 0.9, "keypoints": _kp_asymmetric()}


PIL = object()   # 가짜 — fake embedder/scene 가 실제로 안 씀


# ── 1) 정책: 부적격 축 즉시 거부 ──────────────────────────────────────────────────────────
def t_reject_axis_not_eligible():
    emb = FakeEmbedder({"c": 0.9})
    v = ai_qc.qc_example(PIL, "a hand", intended_axes=["hand_structure"], embedder=emb,
                         scene_analyze=scene_ok())
    assert not v["accepted"], v
    assert any("부적격" in r for r in v["reasons"]), v["reasons"]


# ── 2) 개념 일치 미달 거부 ───────────────────────────────────────────────────────────────
def t_reject_low_concept():
    concept = "single light source study"
    emb = FakeEmbedder({concept: 0.10, RQ["light_direction"]: 0.30})
    v = ai_qc.qc_example(PIL, concept, intended_axes=["light_direction"], embedder=emb,
                         scene_analyze=scene_ok())
    assert not v["accepted"], v
    assert abs(v["checks"]["concept_match"]["cos"] - 0.10) < 1e-4, v["checks"]["concept_match"]
    assert "concept_match" in str(v["reasons"]) or any("개념" in r for r in v["reasons"]), v


# ── 3) 정상 통과 + supports/personas ─────────────────────────────────────────────────────
def t_accept_light():
    concept = "single light source on a sphere"
    emb = FakeEmbedder({concept: 0.30, RQ["light_direction"]: 0.28,
                        RQ["color_harmony"]: 0.05, RQ["value_structure"]: 0.05,
                        RQ["composition_balance"]: 0.05})
    v = ai_qc.qc_example(PIL, concept, intended_axes=["light_direction"], embedder=emb,
                         scene_analyze=scene_ok())
    assert v["accepted"], v
    assert v["supports"] == ["light_direction"], v["supports"]
    assert v["personas"] == ["light"], v["personas"]


# ── 4) 미선언 → 자동 태깅 ────────────────────────────────────────────────────────────────
def t_auto_tag_color():
    concept = "limited warm palette landscape"
    emb = FakeEmbedder({concept: 0.30, RQ["color_harmony"]: 0.27, RQ["light_direction"]: 0.10,
                        RQ["value_structure"]: 0.08, RQ["composition_balance"]: 0.06})
    v = ai_qc.qc_example(PIL, concept, intended_axes=None, embedder=emb, scene_analyze=scene_ok())
    assert v["accepted"], v
    assert v["supports"] == ["color_harmony"], v["supports"]
    assert v["checks"]["axis_policy"].get("auto_tagging") is True


# ── 5) 선언했으나 검증 안 된 축은 drop(통과 유지) ────────────────────────────────────────
def t_drop_unverified_declared():
    concept = "value and light study"
    emb = FakeEmbedder({concept: 0.30, RQ["light_direction"]: 0.28, RQ["value_structure"]: 0.05})
    v = ai_qc.qc_example(PIL, concept, intended_axes=["light_direction", "value_structure"],
                         embedder=emb, scene_analyze=scene_ok())
    assert v["accepted"], v
    assert v["supports"] == ["light_direction"], v["supports"]
    assert "value_structure" in v["checks"]["axis_verify"].get("dropped_declared", []), v


# ── 6) 어떤 적격 축과도 불일치 → 거부 ────────────────────────────────────────────────────
def t_reject_no_axis_verified():
    concept = "something vague"
    emb = FakeEmbedder({concept: 0.30, RQ["light_direction"]: 0.05})
    v = ai_qc.qc_example(PIL, concept, intended_axes=["light_direction"], embedder=emb,
                         scene_analyze=scene_ok())
    assert not v["accepted"], v
    assert any("축" in r for r in v["reasons"]), v["reasons"]


# ── 7) 사진/스샷 거부 ────────────────────────────────────────────────────────────────────
def t_photo_rejected():
    concept = "a color palette"
    emb = FakeEmbedder({concept: 0.40, RQ["color_harmony"]: 0.40})
    v = ai_qc.qc_example(PIL, concept, intended_axes=["color_harmony"], embedder=emb,
                         scene_analyze=scene_ok(analyzable=False, conf=0.2))
    assert not v["accepted"], v
    assert any("일러스트" in r or "그림" in r for r in v["reasons"]), v["reasons"]


# ── 8) 해부 비대칭: strict 거부 / 기본 통과+flag ─────────────────────────────────────────
def t_anatomy_strict_vs_advisory():
    concept = "dramatic side light on a standing figure"
    emb = FakeEmbedder({concept: 0.30, RQ["light_direction"]: 0.28,
                        RQ["value_structure"]: 0.05, RQ["color_harmony"]: 0.05,
                        RQ["composition_balance"]: 0.05})
    common = dict(intended_axes=["light_direction"], embedder=emb,
                  scene_analyze=scene_ok(person=True),
                  pose_extract=pose_asymmetric, hands_detect=hands_none)
    strict = ai_qc.qc_example(PIL, concept, strict_anatomy=True, **common)
    assert not strict["accepted"], strict
    assert "arm_length_asymmetry" in strict["checks"]["anatomy"]["flags"], strict
    advisory = ai_qc.qc_example(PIL, concept, strict_anatomy=False, **common)
    assert advisory["accepted"], advisory
    assert "arm_length_asymmetry" in advisory["anatomy_flags"], advisory


# ── 9) qc_and_ingest: 통과분만 ai_example 로 적재(인자 캡처) ──────────────────────────────
def t_qc_and_ingest_builds_tags():
    concept = "single light source form shadow"
    emb = FakeEmbedder({concept: 0.30, RQ["light_direction"]: 0.28,
                        RQ["value_structure"]: 0.05, RQ["color_harmony"]: 0.05,
                        RQ["composition_balance"]: 0.05})
    captured = {}

    def fake_ingest(pil, **kw):
        captured.update(kw)
        return "ref-123"

    res = ai_ingest.qc_and_ingest(
        PIL, concept, intended_axes=["light_direction"],
        ingest_fn=fake_ingest, audit=False,
        embedder=emb, scene_analyze=scene_ok())
    assert res["accepted"] and res["ref_id"] == "ref-123", res
    assert captured["source_type"] == "ai_example", captured
    assert captured["tags"]["supports"] == ["light_direction"], captured["tags"]
    assert captured["personas"] == ["light"], captured["personas"]
    assert captured["tags"]["concept"] == concept


def t_qc_and_ingest_rejects_without_ingest():
    concept = "blurry nothing"
    emb = FakeEmbedder({concept: 0.05})
    calls = {"n": 0}

    def fake_ingest(pil, **kw):
        calls["n"] += 1
        return "should-not-happen"

    res = ai_ingest.qc_and_ingest(
        PIL, concept, intended_axes=["light_direction"],
        ingest_fn=fake_ingest, audit=False,
        embedder=emb, scene_analyze=scene_ok())
    assert not res["accepted"] and res["ref_id"] is None, res
    assert calls["n"] == 0, "거부면 ingest 를 호출하지 않아야 함"


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 정책·개념일치·축검증·자동태깅·drop·사진거부·해부·적재배선")


if __name__ == "__main__":
    run()
