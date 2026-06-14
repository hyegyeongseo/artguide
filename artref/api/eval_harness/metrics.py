"""'자'. rr(value_range_robust)을 임계로 sweep해 recall-FPR 곡선(ROC) + severity별 recall.
단일 숫자가 아니라 곡선을 내는 이유: 분석기 임계 자체가 튜닝 대상이므로 운용점을 데이터로 고른다."""
from collections import defaultdict


def at_threshold(rows, t):
    tp = fp = tn = fn = 0
    for r in rows:
        pred = (r["rr"] is not None) and (r["rr"] < t)
        if r["defect"] and pred: tp += 1
        elif r["defect"] and not pred: fn += 1
        elif (not r["defect"]) and pred: fp += 1
        else: tn += 1
    return tp / (tp + fn + 1e-9), fp / (fp + tn + 1e-9)


def sweep(rows, lo=0.10, hi=0.60, step=0.05):
    out, t = [], lo
    while t <= hi + 1e-9:
        r, f = at_threshold(rows, t)
        out.append((round(t, 3), round(r, 3), round(f, 3)))
        t += step
    return out


def recall_by_severity(rows, t):
    b = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r["defect"]: continue
        pred = (r["rr"] is not None) and (r["rr"] < t)
        b[r["severity"]][1] += 1
        b[r["severity"]][0] += 1 if pred else 0
    return {s: round(c / n, 3) for s, (c, n) in sorted(b.items())}
