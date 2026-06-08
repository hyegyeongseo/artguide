from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()

def normalize(fp) -> Image.Image:
    img = Image.open(fp)                 # 디코드 실패 → 예외 → 거절
    img = ImageOps.exif_transpose(img)   # 폰 사진 회전 교정
    img = img.convert("RGB")
    img.thumbnail((1536, 1536))
    return img
