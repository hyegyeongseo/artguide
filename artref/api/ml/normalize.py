"""ml/normalize.py — 업로드 정규화(가드 적용). 기존 시그니처 그대로: normalize(fp) -> RGB Image.

기존과 동일한 출력(EXIF 보정·RGB·1536 리사이즈, HEIC 지원)에 더해, 디코드 전에 upload_guard 로
바이트/픽셀/포맷 한도를 강제한다. 위반이면 UploadRejected 가 올라온다(메모리 폭증 없이 거절).

호환: 시그니처·정상 입력 동작은 그대로라 _pipeline 수정 없이 드롭인. 단, 악성·과대 업로드는
이제 예외로 거절되므로, graceful refused 를 원하면 README 의 _pipeline 패치를 적용하세요.
"""
from PIL import Image, ImageOps
import pillow_heif

from ml.upload_guard import safe_open, UploadRejected  # noqa: F401 (재노출)

pillow_heif.register_heif_opener()


def normalize(fp) -> Image.Image:
    img = safe_open(fp)                  # 바이트/픽셀/포맷 가드(폭탄·과대·악성포맷 거절)
    img = ImageOps.exif_transpose(img)   # 폰 사진 회전 교정
    # 투명 배경(알파) 이미지를 그냥 RGB 로 떨구면 투명 영역이 흰색이 돼 밝은 피규어가
    # 흰 카드 위에서 사라진다(예: Blender/Mixamo 백본 렌더). → 알파가 있으면 흰색이 아니라
    # 중립 차콜 위에 합성해 형체가 어디서든 보이게 한다. 불투명 업로드는 기존대로 RGB 변환.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, _ALPHA_BG)
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    img.thumbnail((1536, 1536))
    return img


_ALPHA_BG = (58, 61, 67)   # 투명 합성용 중립 차콜(흰 피규어 대비 확보). 톤은 취향껏 조절 가능.
