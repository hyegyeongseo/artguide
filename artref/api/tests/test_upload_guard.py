"""upload_guard 테스트 — 실제 PIL 로(작은 이미지만 써서 OOM 없이) 가드 경로 검증.

확인:
  1) 정상 작은 PNG 통과.
  2) 픽셀 상한 초과 거절(폭탄 시뮬 — 실제 거대 이미지 대신 max_pixels 를 낮춰 검증).
  3) 바이트 상한 초과 거절.
  4) 허용 안 된 포맷(BMP) 거절.
  5) 디코드 불가(쓰레기 바이트) 거절.
실행: artref/api 에서  python -m tests.test_upload_guard
"""
import os
import sys
import io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from ml import upload_guard as G


def _png(w=16, h=16):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 120, 120)).save(buf, "PNG")
    return buf.getvalue()


def t_ok_small_png():
    img = G.safe_open(_png(32, 32))
    assert img.size == (32, 32) and (img.format or "").upper() == "PNG"


def t_reject_too_many_pixels():
    data = _png(100, 100)             # 10000px
    try:
        G.safe_open(data, max_pixels=1000)   # 한도 1000px → 초과
        assert False, "픽셀 상한 초과인데 통과함"
    except G.UploadRejected as e:
        assert "픽셀" in e.reason, e.reason


def t_reject_too_many_bytes():
    data = _png(64, 64)
    try:
        G.safe_open(data, max_bytes=10)      # 10바이트 한도 → 초과
        assert False, "바이트 상한 초과인데 통과함"
    except G.UploadRejected as e:
        assert "너무 큼" in e.reason, e.reason


def t_reject_disallowed_format():
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (0, 0, 0)).save(buf, "BMP")   # BMP 는 allowlist 밖
    try:
        G.safe_open(buf.getvalue())
        assert False, "BMP 인데 통과함"
    except G.UploadRejected as e:
        assert "포맷" in e.reason, e.reason


def t_reject_garbage():
    try:
        G.safe_open(b"\x00\x01not an image\xff")
        assert False, "쓰레기 바이트인데 통과함"
    except G.UploadRejected as e:
        assert "디코드 불가" in e.reason, e.reason


def t_reject_empty():
    try:
        G.safe_open(b"")
        assert False, "빈 파일인데 통과함"
    except G.UploadRejected as e:
        assert "빈" in e.reason, e.reason


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 정상통과·픽셀상한·바이트상한·포맷·디코드불가·빈파일")


if __name__ == "__main__":
    run()
