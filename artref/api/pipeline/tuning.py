"""pipeline/tuning.py — 진단 스코어러 임계값 튜닝(precision/recall/F1 + sweep).

diagnose.THRESHOLDS 를 override 해 라벨 데이터(신호→발화해야 할 축)에 대한 스코어러 성능을 측정한다.
단일 임계 스코어러는 sweep 으로 최적 임계(F1)를 찾는다. proportion(band)·hand(_hand)는 sweep 대상 아님.

순수 로직(주입 없이 SCORERS/apply_thresholds 만 사용) → DB·CLIP 없이 테스트된다.
실제 라벨은 scripts/extract_signals.py 로 그림에서 신호를 뽑아 사람이 expect 를 붙여 만든다.
"""
from collections import defaultdict

from pipeline.diagnose import SCORERS, apply_thresholds, reset_thresholds, _DEFAULT_THRESHOLDS

# sweep 가능한 단일 임계 키(축 = key.split('.')[0]). value_structure 는 3개 키 중 figure_value_range 대표.
SWEEPABLE = sorted(_DEFAULT_THRESHOLDS)


def fired(signals):
    """현재 THRESHOLDS 로 이 신호에서 발화하는 축 집합."""
    out = set()
    for sid, fn in SCORERS.items():
        try:
            if fn(signals):
                out.add(sid)
        except Exception:
            pass
    return out


def confusion(cases, override=None):
    """cases: [{signals:{...}, expect:[axis,...]}] → {axis: {tp,fp,fn}}. override 적용 후 복원."""
    prev = apply_thresholds(override) if override else None
    try:
        per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
        for c in cases:
            exp = set(c.get("expect", []))
            got = fired(c.get("signals", {}))
            for a in got & exp:
                per[a]["tp"] += 1
            for a in got - exp:
                per[a]["fp"] += 1
            for a in exp - got:
                per[a]["fn"] += 1
    finally:
        if override:
            reset_thresholds()
    return {a: dict(v) for a, v in per.items()}


def prf(cnt):
    tp, fp, fn = cnt["tp"], cnt["fp"], cnt["fn"]
    p = tp / (tp + fp) if (tp + fp) else (1.0 if fn == 0 else 0.0)
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), **cnt}


def metrics(cases, override=None):
    """축별 precision/recall/f1."""
    return {a: prf(c) for a, c in confusion(cases, override).items()}


def frange(lo, hi, step):
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(round(v, 4))
        v += step
    return out


def sweep(cases, key, values):
    """key 임계를 values 로 쓸어 그 축의 P/R/F1 곡선. [{value,precision,recall,f1,tp,fp,fn}]."""
    axis = key.split(".")[0]
    out = []
    for v in values:
        m = metrics(cases, {key: v})
        c = m.get(axis, {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 0})
        out.append({"value": v, "precision": c["precision"], "recall": c["recall"],
                    "f1": c["f1"], "tp": c["tp"], "fp": c["fp"], "fn": c["fn"]})
    return out


def best_threshold(cases, key, values):
    """F1 최대 임계(동률이면 기본값에 가까운 쪽). 반환: (best_row, full_curve)."""
    curve = sweep(cases, key, values)
    if not curve:
        return None, curve
    default = _DEFAULT_THRESHOLDS.get(key, 0.0)
    best = max(curve, key=lambda r: (r["f1"], -abs(r["value"] - default)))
    return best, curve
