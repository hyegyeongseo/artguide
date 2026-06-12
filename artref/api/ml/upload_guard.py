"""ml/upload_guard.py — 업로드 이미지 디코드 하드닝(디컴프레션 폭탄·과대·악성 포맷 방어).

왜: normalize() 가 임의 업로드를 곧장 PIL 로 디코드하는데, 가드가 없으면 작은 악성 파일이
거대한 픽셀로 펼쳐져 메모리를 폭증(OOM-DoS)시킬 수 있다(고전적 이미지 업로드 취약점).
여기서 *디코드 전·직후* 에 한도를 강제한다:
  • 바이트 상한      : UPLOAD_MAX_BYTES (기본 15MB) — 과대 업로드 차단.
  • 픽셀 상한        : UPLOAD_MAX_PIXELS (기본 40MP) — 디컴프레션 폭탄 차단(Image.MAX_IMAGE_PIXELS 동시 설정).
  • 포맷 allowlist   : PNG/JPEG/WEBP/GIF/HEIF/HEIC 만 — 예기치 않은 디코더 경로 축소.

실패는 UploadRejected(reason) 로 올린다. 호출부(normalize)가 그대로 전파하면 엔드포인트는
500 으로 *안전하게* 끝난다(메모리 폭증 없음). graceful 한 'refused' 응답을 원하면 main.py 의
_pipeline 에서 UploadRejected 를 잡아 refused 로 변환하면 된다(README 패치 참고).
"""
import io
import os

from PIL import Image

# HEIC/HEIF 오프너 등록(여기서도 보장 — upload_guard 를 단독 호출해도 안전).
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return int(default)


MAX_BYTES = _int_env("UPLOAD_MAX_BYTES", 15 * 1024 * 1024)     # 15MB
MAX_PIXELS = _int_env("UPLOAD_MAX_PIXELS", 40_000_000)         # 40MP (예: ~6300x6300)

# 디컴프레션 폭탄 전역 가드 — PIL 이 한도 초과 시 DecompressionBombError 를 던지게 한다.
#   여유분(2x)을 둬서 우리의 명시적 size 검사가 먼저 걸리되, 슬립된 경로도 PIL 이 받친다.
Image.MAX_IMAGE_PIXELS = max(MAX_PIXELS * 2, MAX_PIXELS + 1)

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF", "HEIF", "HEIC", "MPO"}  # MPO=일부 JPEG 변종


class UploadRejected(Exception):
    """업로드가 가드에 걸려 거절됨. .reason 에 사람이 읽을 사유."""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _read_bytes(fp):
    """파일류/바이트 → bytes. 바이트 상한 검사. 스트림은 처음으로 되감아 둔다."""
    if isinstance(fp, (bytes, bytearray)):
        data = bytes(fp)
    elif hasattr(fp, "read"):
        try:
            fp.seek(0)
        except Exception:
            pass
        data = fp.read()
    else:
        raise UploadRejected("알 수 없는 입력 타입")
    if not data:
        raise UploadRejected("빈 파일")
    if len(data) > MAX_BYTES:
        raise UploadRejected(f"파일이 너무 큼({len(data)} bytes > 한도 {MAX_BYTES})")
    return data


def safe_open(fp, *, max_pixels=None, max_bytes=None, allowed_formats=None):
    """가드를 통과한 PIL.Image 를 연다(디코드만; 변환은 호출부). 위반이면 UploadRejected.

    검사 순서: 바이트 상한 → 디코드 가능 여부 → 포맷 allowlist → 픽셀 상한.
    픽셀 검사는 Image.open(lazy)의 .size 만으로 하므로 전체 디코드 전에 폭탄을 거른다.
    """
    mp = max_pixels or MAX_PIXELS
    fmts = allowed_formats or ALLOWED_FORMATS
    data = _read_bytes(fp if max_bytes is None else fp)  # max_bytes 무시 시 기본 MAX_BYTES 사용
    if max_bytes is not None and len(data) > max_bytes:
        raise UploadRejected(f"파일이 너무 큼({len(data)} bytes > 한도 {max_bytes})")
    try:
        img = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError as e:
        raise UploadRejected(f"디컴프레션 폭탄 의심: {e}")
    except Exception as e:
        raise UploadRejected(f"이미지로 디코드 불가: {type(e).__name__}")
    fmt = (img.format or "").upper()
    if fmt not in fmts:
        raise UploadRejected(f"허용되지 않은 포맷: {fmt or 'unknown'}")
    try:
        w, h = img.size
    except Exception:
        raise UploadRejected("이미지 크기를 읽을 수 없음")
    if w <= 0 or h <= 0:
        raise UploadRejected("유효하지 않은 이미지 크기")
    if w * h > mp:
        raise UploadRejected(f"이미지 픽셀이 너무 많음({w}x{h} > 한도 {mp}px)")
    return img
