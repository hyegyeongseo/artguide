"""손 탐지기 벤치마크. 사용: (artref/api 에서)
    python -m eval_harness.run_hands <폴더> [--squash]
폴더: hand_*_az*.png 렌더들(평면=전부 clean) 또는 서브폴더 clean/ flat/ foreshorten/(라벨).
--squash: clean 에 2D 세로압축(단축 프록시) 양성 자동 추가(빠른 민감도 확인용)."""
import sys
from .hand_eval import load, run, squash, HandSample, coverage, recall_fpr, by_angle


def main(folder, do_squash=False):
    samples = load(folder)
    if not samples:
        print(f"hand_* 이미지를 못 찾음: {folder}")
        return
    if do_squash:
        samples += [HandSample(squash(s.image), s.path, s.az, s.el, "foreshorten")
                    for s in samples if s.label == "clean"]
    rows = run(samples)
    det, n = coverage(rows)
    print(f"표본 {n}")
    print("\n[이미지별]  검출  파일 — 신호")
    for r in rows:
        mark = "✓" if r["detected"] else "✗"
        tail = f" — {r['signal']}" if r["signal"] else (" — (신호 없음)" if r["detected"] else "")
        print(f"   {mark}  {r['path']}{tail}")
    print(f"\n[탐지 커버리지] {det}/{n} = {det/n:.0%}  ← MediaPipe가 손을 검출한 비율 (가장 중요)")
    if det == 0:
        print("  ⚠ 검출 0 — MediaPipe가 이 렌더에서 손을 못 봅니다. 신호 평가 의미 없음.")
        print("  → 렌더 톤/배경/해상도/모델 점검, 또는 스케치용 검출기 필요. 손 켜기 보류.")
        return
    labels = set(r["label"] for r in rows) - {"clean"}
    for defect in sorted(labels):
        rec, fpr, npos, nneg = recall_fpr(rows, defect)
        tag = "(2D squash 프록시)" if (do_squash and defect == "foreshorten") else ""
        print(f"\n[{defect} 검출] {tag} recall={rec:.2f} (양성 {npos})  FPR={fpr:.2f} (음성 {nneg})")
    print("\n[az 45° 버킷별 신호 발화율] (검출된 것만)  az → 발화/검출")
    for az, (c, nn) in by_angle(rows).items():
        print(f"   az{az:>3}: {c}/{nn}")
    fired = [r for r in rows if r["detected"] and r["fired"]]
    print(f"\n신호 예시: {fired[0]['signal'] if fired else '(발화 없음)'}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else ".", "--squash" in sys.argv)
