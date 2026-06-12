"""extract_signals.py — 실제 그림에서 신호를 뽑아 라벨링용 signals.jsonl 템플릿을 만든다.

부트스트랩 합성 라벨(eval/datasets/signals.json)을 *진짜 그림 기반* 으로 교체/증강하기 위한 도구.
폴더의 각 이미지를 normalize → pose → (pose/image/region/color/light) 신호 추출 → 한 줄씩 jsonl.
expect 는 비워서 내보낸다 → 사람이 "이 그림에서 발화해야 할 축"을 채워 라벨 완성 → tune_thresholds.py 입력.

실행(컨테이너 — pose 가 mediapipe, 신호가 PIL/numpy):
  docker compose exec -w /repo api python scripts/extract_signals.py /repo/labeled_imgs > out.jsonl
  # 그다음 out.jsonl 각 줄의 "expect": [] 를 사람이 채우고 → cases 로 묶어 tune_thresholds.py 에 사용.
"""
import sys
import os
import io
import json

sys.path.insert(0, "api")
from ml.normalize import normalize
from ml.scene import analyze
from ml.pose import extract
from pipeline import diagnose as D

EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def signals_for(pil):
    """diagnose 와 동일한 신호 집합을 한 그림에서 추출(진단 내부 로직과 일치)."""
    scene = analyze(pil)
    pose = extract(scene, pil)
    sig = {}
    if pose.get("status") == "ok":
        sig.update(D.pose_signals(pose["keypoints"]))
    sig.update(D.image_signals(pil))
    sig.update(D.region_signals(pil, pose))
    sig.update(D.color_signals(pil))
    sig.update(D.light_signals(pil, pose))
    # 내부 키(_norms 등)·비직렬화 값 제거, 숫자만
    return {k: float(v) for k, v in sig.items()
            if not k.startswith("_") and isinstance(v, (int, float))}, pose.get("status")


def main():
    if len(sys.argv) < 2:
        print("usage: extract_signals.py <IMAGE_DIR>", file=sys.stderr)
        sys.exit(1)
    folder = sys.argv[1]
    files = sorted(f for f in os.listdir(folder)
                   if os.path.splitext(f)[1].lower() in EXTS)
    for fn in files:
        try:
            with open(os.path.join(folder, fn), "rb") as fh:
                pil = normalize(io.BytesIO(fh.read()))
            sig, pstatus = signals_for(pil)
            rec = {"name": fn, "pose_status": pstatus, "signals": sig, "expect": []}
            print(json.dumps(rec, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"name": fn, "error": f"{type(e).__name__}: {e}"},
                             ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
