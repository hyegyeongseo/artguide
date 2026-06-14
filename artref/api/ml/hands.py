"""ml/hands.py — MediaPipe HandLandmarker (손당 21키포인트, 최대 2손). Phase 3.

pose.py 와 같은 degraded-폴백 패턴: 모델/런타임이 없거나 손 미검출이면 graceful 하게
빈 결과를 돌려 앱이 안 깨지게 한다. 거친 스케치에선 키포인트가 노이즈가 크므로,
여기서 만든 신호의 confidence 는 보수적으로 잡는다(기존 measured 플래그·degraded 캡이
단정 대신 가설형으로 처리하도록).

선행: HandLandmarker .task 모델 파일 필요.
  HAND_TASK 환경변수 또는 기본 경로(/models/hand_landmarker.task)에 두기.
  (다운로드: MediaPipe HandLandmarker 모델 페이지)

⚠️ 2번(라이브러리 확대) 뒤에 켜세요 — region=hand ref가 없으면 손 신호가 떠도 전부 miss.
"""
import os
import math
import tempfile
import urllib.request

_HAND_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")
# pose.py 와 동일 패턴: 모델(.task)을 첫 사용 시 자동 다운로드(약 7MB). HAND_TASK 로 경로 override 가능.
_HAND_TASK = os.environ.get("HAND_TASK", os.path.join(tempfile.gettempdir(), "hand_landmarker.task"))
_landmarker = None
_AVAILABLE = None


def _ensure_model():
    """모델 파일 확보. 없으면 다운로드(pose 와 같은 호스트). 실패하면 False → degraded."""
    if os.path.exists(_HAND_TASK) and os.path.getsize(_HAND_TASK) > 0:
        return True
    try:
        urllib.request.urlretrieve(_HAND_URL, _HAND_TASK)
        return os.path.getsize(_HAND_TASK) > 0
    except Exception as e:
        print(f"[hands] 모델 다운로드 실패(degraded): {type(e).__name__}: {e}")
        return False


def _ensure():
    """lazy 초기화. 실패하면 _AVAILABLE=False 로 두고 이후 호출은 곧장 degraded."""
    global _landmarker, _AVAILABLE
    if _AVAILABLE is not None:
        return _AVAILABLE
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        if not _ensure_model():
            _AVAILABLE = False
            return False
        opts = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=_HAND_TASK),
            num_hands=2, min_hand_detection_confidence=0.3)
        _landmarker = vision.HandLandmarker.create_from_options(opts)
        _AVAILABLE = True
    except Exception as e:
        print(f"[hands] 초기화 실패(degraded): {type(e).__name__}: {e}")
        _AVAILABLE = False
    return _AVAILABLE


def detect(pil):
    """손 검출. 반환: {available, hands:[{landmarks:[(x,y,z)x21], handedness}]}.
    degraded(모델없음/실패/미검출)면 available=False 또는 빈 hands."""
    if not _ensure():
        return {"available": False, "hands": []}
    try:
        import numpy as np
        import mediapipe as mp
        rgb = pil.convert("RGB")
        arr = np.asarray(rgb)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
        res = _landmarker.detect(mp_img)
        hands = []
        for i, lms in enumerate(res.hand_landmarks):
            pts = [(p.x, p.y, p.z) for p in lms]   # 정규화 좌표(0~1), z는 상대깊이
            handed = (res.handedness[i][0].category_name
                      if res.handedness and i < len(res.handedness) else "?")
            hands.append({"landmarks": pts, "handedness": handed})
        return {"available": True, "hands": hands}
    except Exception as e:
        print(f"[hands] 검출 실패(degraded): {type(e).__name__}: {e}")
        return {"available": False, "hands": []}


# ── 손 구조 신호 → diagnose.py 의 s_hand_structure 로 사용 ────────────────
# MediaPipe Hand 인덱스: 0 wrist, 5 index_mcp, 9 middle_mcp, 13 ring_mcp, 17 pinky_mcp,
#                        8 index_tip, 12 middle_tip, ...
def hand_signal(hands):
    """검출된 손에서 '평면 방향'과 '손가락 단축' 신호 → (confidence, signal_text).

    - palm_tilt: 손바닥 평면 법선이 화면을 얼마나 향하는지(정면일수록 큼).
      손목(0)·검지MCP(5)·새끼MCP(17) 세 점의 법선 z성분으로 근사.
    - finger_foreshorten: MCP→TIP 투영 길이가 손 크기 대비 짧으면 단축(손가락이 카메라쪽).
    confidence 는 보수적(최대 0.5). 측정 가능한 손이 있을 때만 > 0.
    """
    if not hands:
        return 0.0, ""
    h = hands[0]["landmarks"]
    if len(h) < 21:
        return 0.0, ""

    def v(i):
        return h[i]

    # 손바닥 평면 법선(세 점 외적)
    import_ok = True
    try:
        w, a, b = v(0), v(5), v(17)
        u = (a[0] - w[0], a[1] - w[1], a[2] - w[2])
        t = (b[0] - w[0], b[1] - w[1], b[2] - w[2])
        nx = u[1] * t[2] - u[2] * t[1]
        ny = u[2] * t[0] - u[0] * t[2]
        nz = u[0] * t[1] - u[1] * t[0]
        nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1e-6
        facing = abs(nz) / nlen          # 1=정면(평면이 화면을 향함), 0=옆면
    except Exception:
        import_ok = False
        facing = 0.0

    # 손가락 단축: 검지 MCP(5)→TIP(8) 투영 길이 / 손 폭(5↔17)
    try:
        idx_mcp, idx_tip = v(5), v(8)
        proj = math.hypot(idx_tip[0] - idx_mcp[0], idx_tip[1] - idx_mcp[1])
        hand_w = math.hypot(v(17)[0] - v(5)[0], v(17)[1] - v(5)[1]) or 1e-6
        ratio = proj / hand_w            # 작을수록 손가락이 카메라 쪽(단축)
    except Exception:
        ratio = 1.0

    parts = []
    conf = 0.0
    if import_ok and facing > 0.6:
        parts.append("손바닥 평면이 화면 정면을 향함")
        conf = max(conf, 0.35)
    elif import_ok and facing < 0.25:
        parts.append("손이 옆면(평면 방향이 화면과 평행)")
        conf = max(conf, 0.3)
    if ratio < 0.6:
        parts.append("손가락이 카메라 쪽으로 단축")
        conf = max(conf, 0.4)

    signal = "; ".join(parts)
    return min(conf, 0.5), signal


# diagnose.py 통합(스케치):
#   from ml.hands import detect as detect_hands, hand_signal
#   hres = detect_hands(pil)
#   if hres["available"]:
#       conf, sig = hand_signal(hres["hands"])
#       if conf > 0:  # 측정된 손 신호 → hand_structure 를 measured 로 승격
#           observations 에 dict(sub_problem="hand_structure", confidence=conf,
#                                signal=sig, measured=True, reference_query=...) 추가/갱신
#   # taxonomy.yaml 의 hand_structure: auto 를 true 로 바꾸면 키워드 없이도 자동 surfacing.
