"""tuning 하니스 테스트 — confusion/PRF/sweep/best_threshold + 임계 복원 보장.
실행: artref/api 에서  python -m tests.test_tuning
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import tuning as T
from pipeline import diagnose as D


CASES = [
    {"signals": {"com_offset": 1.3}, "expect": ["weight_balance"]},   # tp
    {"signals": {"com_offset": 0.95}, "expect": ["weight_balance"]},  # tp
    {"signals": {"com_offset": 0.5}, "expect": []},                   # tn
    {"signals": {"com_offset": 0.95}, "expect": []},                  # fp (발화하지만 라벨 X)
]


def t_confusion_counts():
    con = T.confusion(CASES)
    wb = con["weight_balance"]
    assert wb["tp"] == 2 and wb["fp"] == 1 and wb["fn"] == 0, wb


def t_prf_math():
    m = T.metrics(CASES)["weight_balance"]
    # P = 2/3, R = 2/2 = 1
    assert abs(m["precision"] - 0.667) < 0.01 and m["recall"] == 1.0, m


def t_thresholds_restored_after_override():
    before = D.THRESHOLDS["weight_balance.com_offset"]
    T.metrics(CASES, {"weight_balance.com_offset": 1.5})   # override 사용 후
    assert D.THRESHOLDS["weight_balance.com_offset"] == before, "sweep 후 임계 복원 실패"


def t_sweep_changes_firing():
    # 임계를 1.0 이상으로 올리면 com_offset=0.95 케이스는 발화 안 함 → fp 사라짐
    sw = T.sweep(CASES, "weight_balance.com_offset", [0.9, 1.0, 1.2])
    by = {r["value"]: r for r in sw}
    assert by[0.9]["fp"] >= 1, by[0.9]
    assert by[1.2]["tp"] <= 1, by[1.2]      # 1.3만 남고 0.95는 탈락
    assert D.THRESHOLDS["weight_balance.com_offset"] == 0.9, "복원 확인"


def t_best_threshold_picks_high_f1():
    # 라벨: com_offset>=0.9 면 off. 0.5/0.7=정상, 0.95/1.3=off → 임계 0.8~0.9 부근이 최적
    cases = [
        {"signals": {"com_offset": 0.5}, "expect": []},
        {"signals": {"com_offset": 0.7}, "expect": []},
        {"signals": {"com_offset": 0.95}, "expect": ["weight_balance"]},
        {"signals": {"com_offset": 1.3}, "expect": ["weight_balance"]},
    ]
    best, curve = T.best_threshold(cases, "weight_balance.com_offset",
                                   T.frange(0.5, 1.2, 0.05))
    assert best["f1"] == 1.0, best          # 완벽 분리 가능
    assert 0.7 < best["value"] < 0.96, best


def t_bootstrap_dataset_loads_and_scores():
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "eval", "datasets", "signals.json")
    d = json.load(open(path, encoding="utf-8"))
    cases = d["cases"]
    m = T.metrics(cases)
    # 부트스트랩 라벨에서 주요 축이 합리적 recall 을 내야(스코어러가 라벨과 대체로 일치)
    for axis in ("weight_balance", "color_harmony", "light_direction"):
        assert m[axis]["recall"] >= 0.6, (axis, m[axis])


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — confusion·PRF·복원·sweep·best·부트스트랩로드")


if __name__ == "__main__":
    run()
