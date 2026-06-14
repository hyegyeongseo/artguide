"""변형 = 라벨 자동 생성. clean(음성, 결함 없음) + 압축(양성, severity별).
음성은 *깨끗함을 아는* 원본이어야 함(전체 명도폭 넓은 그림). real/synthetic 은 도메인 전이 확인용 메타."""
from dataclasses import dataclass
from PIL import Image
from .transforms import compress_range, to_gray


@dataclass
class Sample:
    image: Image.Image
    defect: bool          # 정답: '명도 폭 좁음' 결함을 주입했나
    severity: float       # 0=clean, 클수록 강한 압축
    meta: dict


DEFAULT_KS = (0.75, 0.55, 0.35)   # 약/중/강 압축 → severity 0.25/0.45/0.65


def generate(images, ks=DEFAULT_KS, source="real"):
    ds = []
    for i, img in enumerate(images):
        ds.append(Sample(to_gray(img), False, 0.0, {"src": i, "t": "none", "source": source}))
        for k in ks:
            ds.append(Sample(compress_range(img, k), True, round(1 - k, 2),
                             {"src": i, "t": f"compress_{k}", "source": source}))
    return ds
