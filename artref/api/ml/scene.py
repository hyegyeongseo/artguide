import numpy as np
from ml.embed import embedder

LABELS = {
  "subject":  ["a person", "no person, landscape or still life"],
  "type":     ["a photo or screenshot or document", "an artwork or drawing"],
  "camera":   ["low angle view", "high angle view", "eye level"],
  "lighting": ["dramatic lighting", "flat even lighting"],
}

def _scores(img_vec, labels):
    sims = [float(np.dot(img_vec, embedder.text(l))) for l in labels]
    e = np.exp(sims - np.max(sims)); p = e / e.sum()      # softmax → confidence
    return dict(zip(labels, p.tolist()))

def analyze(pil) -> dict:
    iv = embedder.image(pil)
    subj = _scores(iv, LABELS["subject"])
    typ  = _scores(iv, LABELS["type"])
    person_p = subj["a person"]
    analyzable = typ["an artwork or drawing"] > 0.5
    return {
      "analyzable": analyzable,
      "global": {"confidence": max(typ.values())},
      "subject": {"person": {"present": person_p > 0.5, "prominence": person_p}},
      "framing": {"camera": _scores(iv, LABELS["camera"])},    # 낮은 신뢰도 힌트
      "render":  {"lighting": _scores(iv, LABELS["lighting"])},# hard 분기 금지
    }
