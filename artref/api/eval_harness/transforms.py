"""합성 변형 = 주입 결함이 곧 정답. 명암 분석기는 '명도 범위(value range)'를 재므로 변형도 *범위 압축*.
밝은 종이면 종이보다 어두운 자국만 압축(평면 스케치 모사), 톤 배경/흉상이면 전체를 평균 쪽으로 압축
(인물 명도 폭을 직접 좁힘) — 둘 다 '인물 명도 폭 좁음' 결함을 분석기가 재는 형태로 주입한다."""
import numpy as np
from PIL import Image


def to_gray(img):
    return img.convert("L")


def compress_range(img, k):
    a = np.asarray(img.convert("L"), float) / 255.0
    h, _ = np.histogram(a.ravel(), bins=32, range=(0.0, 1.0))
    mode = (int(h.argmax()) + 0.5) / 32.0
    out = a.copy()
    if mode > 0.60:                                  # 밝은 종이: 자국(종이보다 어두운)만 압축
        sub = a < mode - 0.06
        if sub.any():
            m = a[sub].mean()
            out[sub] = np.clip(m + (a[sub] - m) * k, 0, 1)
    else:                                            # 톤 배경/흉상: 전체를 평균 쪽으로 압축
        m = a.mean()
        out = np.clip(m + (a - m) * k, 0, 1)
    return Image.fromarray((out * 255).astype("uint8"))
