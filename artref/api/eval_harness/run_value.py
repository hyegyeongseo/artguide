"""명암 축 end-to-end + baseline↔마스크 비교.
사용: (artref/api 에서) python -m eval_harness.run_value <원본폴더> [--mask-only|--base-only]
원본폴더엔 *명도폭 넓은 깨끗한 그림*을 넣을 것(음성=false positive 기준).
각 분석기에 대해 커버리지(측정 가능 장수) + 현재 임계 recall/FPR + severity별 recall + ROC 출력."""
import sys, glob, os
from PIL import Image
from .dataset import generate
from .analyzer import analyze_value, analyze_value_masked
from .metrics import at_threshold, sweep, recall_by_severity

DEF_T = 0.35


def _rows(ds, fn):
    out = []
    for s in ds:
        rr = fn(s.image)["rr"]
        out.append({"rr": rr, "defect": s.defect, "severity": s.severity})
    return out


def _report(name, rows):
    n = len(rows); cov = sum(r["rr"] is not None for r in rows)
    r, f = at_threshold(rows, DEF_T)
    print(f"\n===== {name} =====")
    print(f"커버리지(측정가능): {cov}/{n}    ← rr=None 이면 '측정 보류'(못 잼)")
    print(f"[현재 임계 {DEF_T}] recall={r:.2f}  FPR={f:.2f}")
    print(f"[severity별 recall @ {DEF_T}] {recall_by_severity(rows, DEF_T)}")
    print(" ROC:  t   recall  FPR")
    for t, rc, fp in sweep(rows):
        print(f"      {t:.2f}   {rc:.2f}   {fp:.2f}")


def main(folder, mode="both"):
    paths = [p for p in sorted(glob.glob(os.path.join(folder, "*")))
             if p.lower().endswith((".png", ".jpg", ".jpeg"))]
    imgs = [Image.open(p) for p in paths]
    ds = generate(imgs)
    pos = sum(s.defect for s in ds)
    print(f"표본 {len(ds)} (원본 {len(imgs)} · 음성 {len(ds) - pos} · 양성 {pos})")
    if mode in ("both", "base"):
        _report("BASELINE (degraded · 마스크 없음)", _rows(ds, analyze_value))
    if mode in ("both", "mask"):
        _report("MASKED (피사체 마스크)", _rows(ds, analyze_value_masked))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = "mask" if "--mask-only" in sys.argv else "base" if "--base-only" in sys.argv else "both"
    main(args[0] if args else ".", mode)
