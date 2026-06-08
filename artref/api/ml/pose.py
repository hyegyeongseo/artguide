"""포즈 키포인트 추출 — mediapipe Tasks API(PoseLandmarker).

레거시 mp.solutions는 최신 protobuf와 충돌해 깨지므로(0.10.35 + protobuf 7),
현대 Tasks API를 쓴다. 모델(.task)은 첫 사용 시 다운로드(약 5MB). 33 키포인트 토폴로지는
레거시와 동일하므로 diagnose의 keypoint 로직은 그대로 동작한다.

어떤 단계든 실패하면(import·모델·추론) 예외를 삼키고 degraded로 폴백 → API는 항상 기동.
"""
import os, tempfile, urllib.request
import numpy as np

VIS = 0.5
_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
              "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")
_MODEL_PATH = os.path.join(tempfile.gettempdir(), "pose_landmarker_lite.task")

_detector = None
_ready = None  # None=미시도, True=가능, False=불가


def _ensure_model():
    if os.path.exists(_MODEL_PATH) and os.path.getsize(_MODEL_PATH) > 0:
        return True
    try:
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        return os.path.getsize(_MODEL_PATH) > 0
    except Exception as e:
        print(f"[pose] 모델 다운로드 실패 → 포즈 비활성: {type(e).__name__}: {e}")
        return False


def _get_detector():
    global _detector, _ready
    if _ready is not None:
        return _detector
    try:
        if not _ensure_model():
            _detector, _ready = None, False
            return None
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        opts = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_poses=1)
        _detector = mp_vision.PoseLandmarker.create_from_options(opts)
        _ready = True
        print("[pose] mediapipe Tasks PoseLandmarker 준비 완료")
    except Exception as e:
        print(f"[pose] mediapipe Tasks 초기화 실패 → 포즈 비활성: {type(e).__name__}: {e}")
        _detector, _ready = None, False
    return _detector


def extract(scene, pil):
    det = _get_detector()
    if det is None:
        return {"status": "skipped", "reason": "pose_unavailable"}
    try:
        import mediapipe as mp
        rgb = np.array(pil.convert("RGB"), dtype=np.uint8)
        res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    except Exception as e:
        print(f"[pose] 추론 실패 → skipped: {type(e).__name__}: {e}")
        return {"status": "skipped", "reason": "pose_error"}
    if not res.pose_landmarks:
        return {"status": "skipped", "reason": "no_person_detected"}
    lms = res.pose_landmarks[0]  # 첫 인물 (33 keypoints, BlazePose 순서)
    def v(p):
        return float(getattr(p, "visibility", 1.0) or 0.0)
    mean_vis = float(np.mean([v(p) for p in lms])) if lms else 0.0
    status = "ok" if mean_vis >= VIS else "low_confidence"
    return {"status": status, "mean_visibility": mean_vis,
            "keypoints": [(p.x, p.y, v(p)) for p in lms]}
