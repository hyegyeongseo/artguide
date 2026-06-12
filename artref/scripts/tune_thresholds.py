"""tune_thresholds.py — 신호 라벨 데이터로 스코어러 임계값을 측정·sweep.

현재 임계의 축별 P/R/F1 을 출력하고, 단일 임계 키마다 sweep 해 F1 최적값을 제안한다.
제안 임계는 자동 반영하지 않는다 — 검토 후 DX_THRESHOLDS(env) 또는 _DEFAULT_THRESHOLDS 로 적용.

실행:
  cd artref && python -m pytest 없이:  PYTHONPATH=api python scripts/tune_thresholds.py eval/datasets/signals.json
  (또는 컨테이너)  docker compose exec -w /repo api python scripts/tune_thresholds.py eval/datasets/signals.json
"""
import sys
import os
import json

sys.path.insert(0, "api")
from pipeline import tuning as T
from pipeline.diagnose import _DEFAULT_THRESHOLDS


def _load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["cases"] if isinstance(d, dict) and "cases" in d else d


# 키별 sweep 범위(lo, hi, step). 방향(>/< )과 무관 — F1 최적을 찾는다.
SWEEP_RANGE = {
    "weight_balance.com_offset": (0.5, 1.4, 0.05),
    "foreshortening.arm_proj_ratio": (0.4, 0.9, 0.02),
    "action_line.torso_lean": (0.01, 0.06, 0.002),
    "joint_articulation.angle_max": (165, 182, 1),
    "value_structure.figure_value_range": (0.2, 0.5, 0.01),
    "value_structure.value_std": (0.1, 0.25, 0.005),
    "value_structure.figure_bg_contrast": (0.04, 0.14, 0.005),
    "composition_balance.focus_centeredness": (0.8, 0.99, 0.01),
    "color_harmony.sat_mean": (0.4, 0.85, 0.02),
    "color_harmony.hue_spread": (0.3, 0.8, 0.02),
    "light_direction.light_ramp": (0.005, 0.03, 0.001),
}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "eval/datasets/signals.json"
    cases = _load(path)
    print(f"케이스 {len(cases)}개\n")

    print("== 현재 임계 성능(축별) ==")
    m = T.metrics(cases)
    print(f"{'axis':22}{'P':>7}{'R':>7}{'F1':>7}{'tp':>5}{'fp':>5}{'fn':>5}")
    for axis in sorted(m):
        c = m[axis]
        print(f"{axis:22}{c['precision']:>7}{c['recall']:>7}{c['f1']:>7}"
              f"{c['tp']:>5}{c['fp']:>5}{c['fn']:>5}")

    print("\n== 임계 sweep(F1 최적 제안) ==")
    print(f"{'key':40}{'현재':>8}{'제안':>8}{'F1현재':>8}{'F1제안':>8}")
    for key, (lo, hi, step) in SWEEP_RANGE.items():
        vals = T.frange(lo, hi, step)
        best, curve = T.best_threshold(cases, key, vals)
        cur = _DEFAULT_THRESHOLDS[key]
        cur_row = min(curve, key=lambda r: abs(r["value"] - cur)) if curve else {"f1": 0}
        flag = "  *" if best and abs(best["value"] - cur) > step else ""
        print(f"{key:40}{cur:>8.3f}{best['value']:>8.3f}{cur_row['f1']:>8}{best['f1']:>8}{flag}")
    print("\n*  = 현재값과 다른 임계가 더 나은 F1(검토 후 적용). 적용: DX_THRESHOLDS env(JSON) 또는 _DEFAULT_THRESHOLDS.")
    print("주의: 위 signals.json 은 부트스트랩(합성)입니다. 실제 그림 라벨(extract_signals.py)로 교체 후 신뢰하세요.")


if __name__ == "__main__":
    main()
