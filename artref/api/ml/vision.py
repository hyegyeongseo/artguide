"""ml/vision.py — Gemini VLM 손 *관찰자*. 검출(MediaPipe) 없이 그림을 관찰한다.

원칙(artcoach): 측정=사실, *관찰=가설*, 코칭=서술. 이 관찰은 측정이 아니므로 '관찰(가설)'로만 surface.
신뢰 장치:
  - 구조화 JSON 출력 → 두 번 호출의 일관성을 *기계적으로* 비교(자유 텍스트는 비교 불가).
  - 2회 중 view·structure 가 일치할 때만 confidence='관찰', 아니면 '낮음'(파이프라인이 구체관찰 surface 보류).
  - 출력 방어선: coach 가드레일과 동일한 FORBIDDEN 정책표현이 새면 그 실행 폐기.
게이트: HAND_VLM(기본 0). 백엔드: VLM_BACKEND=aistudio(기본, GEMINI_API_KEY) | vertex(GCP 크레딧, ADC).
  vertex: GOOGLE_CLOUD_PROJECT/LOCATION + GOOGLE_APPLICATION_CREDENTIALS(서비스계정 JSON). 모델·body·응답 동일.

자가검증:  python -m ml.vision --selftest          (키 없이 일관성 로직 테스트)
실시간:    HAND_VLM=1 python -m ml.vision <이미지>   (Gemini 실제 호출)
"""
import os
import io
import re
import json
import time
import base64
import requests

_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

# 백엔드: aistudio(기본, API 키) | vertex(GCP 크레딧, ADC 인증). body·응답 형식은 동일.
_BACKEND = os.environ.get("VLM_BACKEND", "aistudio").strip().lower()
_VX_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_VX_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
_VX_CREDS = None  # ADC 자격증명 캐시(토큰은 만료 시 자동 refresh)


def _vertex_token():
    """ADC(GOOGLE_APPLICATION_CREDENTIALS 서비스계정 또는 메타데이터)로 OAuth 액세스 토큰."""
    global _VX_CREDS
    from google.auth import default                       # pip install google-auth
    from google.auth.transport.requests import Request
    if _VX_CREDS is None:
        _VX_CREDS, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not _VX_CREDS.valid:
        _VX_CREDS.refresh(Request())
    return _VX_CREDS.token

# 검증된 v2 관찰 프롬프트를 구조화 JSON 으로. verdict 질문 없음, 평가어 금지.
_PROMPT = (
    "그림에 그려진 '손 하나'를 관찰합니다. 평가·판정 금지 — "
    "'부족/어색/틀림/실력/잘함/못함' 같은 말 금지. 보이는 사실만.\n"
    "아래 JSON 객체 하나만 출력하세요(마크다운·설명·코드펜스 없이 순수 JSON):\n"
    '{\n'
    '  "view": "손등"|"손바닥"|"옆면"|"불확실",\n'
    '  "plane_facing": "손 평면이 향하는 방향(짧게, 예: 아래-오른쪽)",\n'
    '  "foreshortening": ["단축되어 보이는 손가락/부위", ...],  // 없으면 []\n'
    '  "structure": "입체"|"평면"|"혼합",\n'
    '  "notes": "보이는 사실 한 문장"\n'
    '}\n'
    'structure 는 그려진 방식의 관찰입니다(덩어리로 읽히면 "입체", 외곽선 위주면 "평면"). 잘잘못이 아닙니다.\n'
    '보이지 않으면 값에 "불확실". 반드시 JSON 하나만.'
)

# 출력 방어선: coach 가드레일(safety/validate.py)과 동일 어휘. import 실패 시 동일 패턴 폴백.
try:
    from safety.validate import FORBIDDEN
except Exception:  # pragma: no cover
    FORBIDDEN = re.compile(r"(초보|실력|등급|점수|재능 ?없|잘 그렸|못 그렸|대신 그려|정답 ?이미지)")

_VIEWS = {"손등", "손바닥", "옆면", "불확실"}
_STRUCT = {"입체", "평면", "혼합", "불확실"}


def _on():
    return os.environ.get("HAND_VLM", "0").strip().lower() not in ("", "0", "false", "no")


def _key():
    return os.environ.get("GEMINI_API_KEY", "")


def _creds_ok():
    """백엔드별 자격 존재 확인. vertex 는 project 만 보고(ADC 인증은 호출 시점), aistudio 는 키."""
    if _BACKEND == "vertex":
        return bool(_VX_PROJECT)
    return bool(_key())


def _vertex_url(model):
    """리전: {loc}-aiplatform.googleapis.com. global: aiplatform.googleapis.com(접두사 없음).
    global 은 용량 인식 라우팅으로 429 를 줄여 권장됨(gemini-2.5-flash 지원)."""
    loc = _VX_LOCATION
    host = "aiplatform.googleapis.com" if loc == "global" else (loc + "-aiplatform.googleapis.com")
    return ("https://" + host + "/v1/projects/" + _VX_PROJECT
            + "/locations/" + loc + "/publishers/google/models/" + model + ":generateContent")


def _request(model, body, timeout, key):
    """백엔드별 (url, params, headers) 로 POST. body·응답 형식은 동일."""
    if _BACKEND == "vertex":
        url = _vertex_url(model)
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + _vertex_token()}
        params = {}
    else:
        url = _URL.format(m=model)
        headers = {"Content-Type": "application/json"}
        params = {"key": key}
    return requests.post(url, params=params, headers=headers,
                         data=json.dumps(body), timeout=timeout)


def _to_b64(image):
    """경로(str) 또는 PIL.Image 를 (base64, mime) 로."""
    if isinstance(image, str):
        with open(image, "rb") as f:
            data = f.read()
        mime = "image/png" if image.lower().endswith(".png") else "image/jpeg"
        return base64.b64encode(data).decode(), mime
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def _redact(msg, key):
    """에러 메시지에서 키 노출 차단(URL 의 ?key= 등)."""
    return msg.replace(key, "***KEY***") if key else msg


def _call(b64, mime, key, model=_MODEL, timeout=90, retries=2):
    """Gemini 호출(aistudio 키 또는 vertex ADC). 429 면 백오프 후 제한 재시도. 에러의 키는 마스킹.
    production: 429 가 끝까지면 예외 → observe_hand 가 삼켜 None(폴백). eval: 하니스가 throttle 로 예방.
    """
    body = {"contents": [{"role": "user", "parts": [
        {"text": _PROMPT},
        {"inline_data": {"mime_type": mime, "data": b64}}]}]}
    for attempt in range(retries + 1):
        r = _request(model, body, timeout, key)
        if r.status_code == 429 and attempt < retries:
            time.sleep(2 * (2 ** attempt))          # 2s, 4s
            continue
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            body = ""
            try:
                body = " | 응답: " + r.text[:600]
            except Exception:
                pass
            raise requests.HTTPError(_redact(str(e) + body, key)) from None
        j = r.json()
        return j["candidates"][0]["content"]["parts"][0]["text"]


def _parse(raw):
    """모델 텍스트에서 JSON 추출·정규화. 실패하면 None."""
    if not raw:
        return None
    t = raw.strip().replace("```json", "").replace("```", "").strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        d = json.loads(t[a:b + 1])
    except Exception:
        return None
    view = str(d.get("view", "불확실")).strip()
    struct = str(d.get("structure", "불확실")).strip()
    fs = d.get("foreshortening", []) or []
    if not isinstance(fs, list):
        fs = [str(fs)]
    return {
        "view": view if view in _VIEWS else "불확실",
        "plane_facing": str(d.get("plane_facing", "")).strip(),
        "foreshortening": [str(x).strip() for x in fs if str(x).strip()],
        "structure": struct if struct in _STRUCT else "불확실",
        "notes": str(d.get("notes", "")).strip(),
    }


_FINGER = {"가운데": "중지", "중간": "중지", "검지": "검지", "집게": "검지",
           "약지": "약지", "넷째": "약지", "새끼": "소지", "소지": "소지",
           "엄지": "엄지", "첫째": "엄지", "중지": "중지"}


def _norm(s):
    s = s.strip()
    for k, v in _FINGER.items():
        if k in s:
            return v
    return s


def _agree(a, b):
    """일관성: view·structure 가 일치(또는 한쪽이 '불확실')하면 True. 단축은 더 미세해 별도 처리."""
    if not a or not b:
        return False
    if a["view"] != b["view"] and "불확실" not in (a["view"], b["view"]):
        return False
    if a["structure"] != b["structure"] and "불확실" not in (a["structure"], b["structure"]):
        return False
    return True


def observe_hand(image, runs=2):
    """그림 속 손 하나를 관찰(가설). 게이트 off·키 없음·전부 실패면 None.
    반환: dict(view, plane_facing, foreshortening, structure, notes, consistent, confidence, runs_used).
    foreshortening 은 두 실행의 *교집합*만 남긴다(일관된 단축만 신뢰).
    """
    if not _on() or not _creds_ok():
        return None
    b64, mime = _to_b64(image)
    key = _key()
    parsed = []
    for _ in range(runs):
        try:
            raw = _call(b64, mime, key)
        except Exception:
            continue
        p = _parse(raw)
        if not p:
            continue
        if FORBIDDEN.search(p["notes"] + " " + p["plane_facing"]):  # 방어선
            continue
        parsed.append(p)
    if not parsed:
        return None

    base = parsed[0]
    consistent = len(parsed) >= 2 and _agree(parsed[0], parsed[1])
    fs = base["foreshortening"]
    if consistent and len(parsed) >= 2:
        s2 = {_norm(x) for x in parsed[1]["foreshortening"]}
        fs = [x for x in fs if _norm(x) in s2]
    return {
        "model": _MODEL,
        "view": base["view"],
        "plane_facing": base["plane_facing"],
        "foreshortening": fs,
        "structure": base["structure"],
        "notes": base["notes"] if consistent else "",
        "consistent": consistent,
        "confidence": "관찰" if consistent else "낮음",
        "runs_used": len(parsed),
    }


def _selftest():
    """키 없이 파싱·일관성 로직 검증."""
    r1 = '{"view":"손등","plane_facing":"아래-오른쪽","foreshortening":["중지","약지"],"structure":"입체","notes":"손등이 보인다"}'
    r2 = '```json\n{"view":"손등","plane_facing":"오른쪽 아래","foreshortening":["가운데 손가락","약지"],"structure":"입체","notes":"손등 보임"}\n```'
    r3 = '{"view":"손바닥","plane_facing":"위","foreshortening":[],"structure":"평면","notes":"x"}'
    a, b, c = _parse(r1), _parse(r2), _parse(r3)
    assert a and b and c, "parse 실패"
    assert _agree(a, b) is True, "일치해야 함(view·structure 같음)"
    assert _agree(a, c) is False, "불일치여야 함(view·structure 다름)"
    # 단축 교집합: 중지·약지 (가운데→중지 정규화)
    inter = [x for x in a["foreshortening"] if _norm(x) in {_norm(y) for y in b["foreshortening"]}]
    assert set(_norm(x) for x in inter) == {"중지", "약지"}, f"교집합 오류: {inter}"
    # 정책표현 방어선
    assert FORBIDDEN.search("이건 실력이 부족"), "FORBIDDEN 동작 확인"
    print("selftest OK — 파싱·일관성·교집합·방어선 정상")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--selftest" in args:
        _selftest()
        raise SystemExit
    os.environ.setdefault("HAND_VLM", "1")  # 수동 실행 편의
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("사용: HAND_VLM=1 python -m ml.vision <이미지>  |  python -m ml.vision --selftest")
        raise SystemExit
    for p in paths:
        out = observe_hand(p, runs=2)
        print(f"\n[{os.path.basename(p)}]")
        print(json.dumps(out, ensure_ascii=False, indent=2) if out else "None (게이트 off / 키 없음 / 호출·파싱 실패)")
