"""eval_harness/hand_eval.py — 손 탐지기(ml.hands.detect + hand_signal) 벤치마크.

손은 명암과 다르다:
  · 헤드라인은 *탐지 커버리지* — MediaPipe(사진 학습)가 렌더/스케치에서 손을 애초에 검출하나.
    낮으면 신호 품질은 무의미하고, 손 기능 자체가 무력하다.
  · 진짜 평면화/단축은 3D 렌더 측에서 해야 정확(2D 변형은 프록시). 그래서 라벨 폴더
    (clean/ flat/ foreshorten/)를 받아 백본 렌더 왜곡을 직접 채점할 수도 있게 한다.
  · 렌더 각도(파일명 az/el)는 공짜 정답 — facing/단축 신호가 실제 각도와 맞는지 sanity.
"""
import os, re, glob
from dataclasses import dataclass
from collections import defaultdict
from PIL import Image

_AZ = re.compile(r"az(-?\d+)", re.I)
_EL = re.compile(r"el(-?\d+)", re.I)


@dataclass
class HandSample:
    image: Image.Image
    path: str
    az: int
    el: int
    label: str          # 'clean' | 'flat' | 'foreshorten' | ...(서브폴더명; 없으면 clean)


def _meta(path):
    n = os.path.basename(path)
    a = _AZ.search(n); e = _EL.search(n)
    return (int(a.group(1)) if a else None, int(e.group(1)) if e else None)


def _ok(p, hand_only):
    if not p.lower().endswith((".png", ".jpg", ".jpeg")):
        return False
    return (not hand_only) or ("hand" in os.path.basename(p).lower())


def load(folder, hand_only=True):
    """folder 직접(=전부 clean) 또는 서브폴더(clean/ flat/ foreshorten/)를 라벨로. hand_* 만(foot 제외)."""
    out, subs = [], [d for d in glob.glob(os.path.join(folder, "*")) if os.path.isdir(d)]
    targets = ([(d, os.path.basename(d)) for d in subs] if subs else [(folder, "clean")])
    for d, label in targets:
        for p in sorted(glob.glob(os.path.join(d, "*"))):
            if _ok(p, hand_only):
                az, el = _meta(p)
                out.append(HandSample(Image.open(p), p, az, el, label))
    return out


def squash(img, k=0.6):
    """2D 프록시: 세로 압축 후 흰 패딩 → 검지 투영이 짧아져 '단축' 모사. 진짜 단축은 3D 렌더 측."""
    w, h = img.size
    small = img.resize((w, max(1, int(h * k))))
    canvas = Image.new(img.convert("RGB").mode, (w, h), (255, 255, 255))
    canvas.paste(small.convert("RGB"), (0, (h - small.size[1]) // 2))
    return canvas


def run(samples, detect=None, hand_signal=None):
    """ml.hands.detect + hand_signal 을 각 이미지에 적용. (실제 탐지기와의 *유일한* 접점.)
    detect/hand_signal 주입 가능(테스트용 mock). 기본은 진짜 ml.hands."""
    if detect is None or hand_signal is None:
        from ml.hands import detect as _d, hand_signal as _h
        detect = detect or _d; hand_signal = hand_signal or _h
    rows = []
    for s in samples:
        name = os.path.basename(s.path)
        h = detect(s.image)
        if not h.get("available") or not h.get("hands"):
            rows.append({"detected": False, "fired": False, "conf": 0.0, "signal": "",
                         "az": s.az, "label": s.label, "path": name})
            continue
        conf, sig = hand_signal(h["hands"])
        rows.append({"detected": True, "fired": conf > 0, "conf": float(conf),
                     "signal": sig, "az": s.az, "label": s.label, "path": name})
    return rows


# ── 지표 ──────────────────────────────────────────────────────────────────────
def coverage(rows):
    return sum(r["detected"] for r in rows), len(rows)


# 라벨 → 그 결함에서 *기대되는 신호 키워드*. hand_signal 은 결함 탐지기가 아니라 방향 관찰자라
# (정면/옆면은 결함이 아님), '단축'만이 그리기-난이도 마커. flat 등은 3D 렌더 라벨이 있을 때만 의미.
DEFECT_KEY = {"foreshorten": "단축", "flat": "정면", "side": "옆면"}


def recall_fpr(rows, defect="foreshorten"):
    """라벨 모드: defect 라벨에서 *해당 신호 키워드* 발화=recall, clean에서 발화=FPR.
    탐지 실패는 miss(발화 안 함)로 셈 → 커버리지 낮으면 recall 상한도 낮아진다(정직)."""
    key = DEFECT_KEY.get(defect, "")
    pos = [r for r in rows if r["label"] == defect]
    neg = [r for r in rows if r["label"] == "clean"]
    rec = sum(key in r["signal"] for r in pos) / (len(pos) or 1)
    fpr = sum(key in r["signal"] for r in neg) / (len(neg) or 1)
    return rec, fpr, len(pos), len(neg)


def by_angle(rows):
    """검출된 손의 az 45° 버킷별 발화율 — facing/단축이 각도와 맞는지 sanity."""
    b = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["detected"] and r["az"] is not None:
            k = (r["az"] % 360) // 45 * 45
            b[k][1] += 1
            b[k][0] += 1 if r["fired"] else 0
    return {k: (c, n) for k, (c, n) in sorted(b.items())}
