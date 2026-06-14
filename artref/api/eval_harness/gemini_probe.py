"""eval_harness/gemini_probe.py — Gemini vision *지각* 테스트 (VLM 손 관찰자의 measure-before-build).

MediaPipe가 실패한 바로 그 손 스케치들을 Gemini 에 보내, '정확히 관찰하나'를 사람이 눈으로 채점한다.
SDK 불필요 — requests 로 AI Studio REST 호출(GEMINI_API_KEY 재사용). GCP 크레딧(Vertex)은 인증만 다름.

사용: (artref/api 에서)
    docker compose exec -w /repo/api -e GEMINI_API_KEY=$KEY api \
        python -m eval_harness.gemini_probe /repo/samples/handtest/hand_sketch1.jpg [more...]
판정: 출력된 관찰이 *실제 그림과 맞나*. 맞으면 → VLM 손 관찰자 빌드 청신호(단 충실도 eval 동반).
      틀린 걸 자신있게 말하면(환각) → 주의. 그게 우리가 피해온 위험이다.
"""
import os, sys, base64, json
import requests

_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

# 관찰 전용 프롬프트 — verdict 유발하던 (4)를 제거. '부족/어색/틀림' 같은 평가어 금지.
# 손 하나만 가정(어수선한 시트는 한 손을 크롭해서 넣을 것 → 개수 환각 제거).
_PROMPT = (
    "이 그림에 그려진 '손 하나'를 관찰만 하세요. 평가·판정 금지 — "
    "'부족/어색/틀림/약함/좋음/잘함/못함/실력/볼륨감 부족' 같은 말을 쓰지 마세요. 보이는 사실만:\n"
    "(1) 방향: 손바닥과 손등 중 무엇이 보이나, 평면이 어디를 향하나(정면/옆면/위/아래), 손가락 끝은 어디를 향하나.\n"
    "(2) 단축: 손가락이나 손이 보는 쪽으로 짧아져 보이는 부분이 있나(있으면 어디).\n"
    "(3) 구조: 손바닥(상자)+손가락(원통)의 입체 덩어리로 읽히나, 외곽선 위주의 평면으로 읽히나. "
    "이건 '그려진 방식'의 관찰이지 잘잘못이 아닙니다.\n"
    "보이지 않으면 '판단 보류'. 짧고 사실적으로."
)


def _mime(path):
    p = path.lower()
    return "image/png" if p.endswith(".png") else "image/jpeg"


def observe(path, key, model=_MODEL):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = {"contents": [{"parts": [
        {"text": _PROMPT},
        {"inline_data": {"mime_type": _mime(path), "data": b64}}]}]}
    r = requests.post(_URL.format(m=model), params={"key": key},
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(body), timeout=90)
    r.raise_for_status()
    j = r.json()
    return j["candidates"][0]["content"]["parts"][0]["text"].strip()


def main(paths, runs=2):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("GEMINI_API_KEY 가 비어 있습니다(백엔드 환경에만 설정). "
              "docker compose exec -e GEMINI_API_KEY=... 로 주입하세요.")
        return
    print(f"모델: {_MODEL}  ·  {runs}회 호출(일관성 확인)\n")
    for p in paths:
        print("=" * 60)
        print(f"[{os.path.basename(p)}]")
        for i in range(runs):
            print(f"  ── {i + 1}회차 ──")
            try:
                print(observe(p, key))
            except Exception as e:
                print(f"  실패: {type(e).__name__}: {e}")
            print()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    runs = 2
    for a in sys.argv[1:]:
        if a.startswith("--runs="):
            runs = int(a.split("=", 1)[1])
    main(args or [], runs)
