"""피사체 마스크 — pose 검출이 실패하는(degraded) 흉상/얼굴/저키에서도 figure 영역을 잡아
region_signals(figure_value_range / figure_bg_contrast)를 채운다. 정확한 외곽선이 아니라
'배경을 빼고 인물 명도를 재는' 게 목적이라 거친 마스크로 충분. 품질은 eval 하니스로 판정.

새 의존성 0 — numpy + PIL 만 사용(컨테이너에 cv2/scipy 없음).
  paper   : 밝은 종이 위 스케치 → 종이보다 어두운 자국(임계). 흰 종이 스케치용.
  salient : 톤 배경/흉상 → rembg(설치돼 있으면, 최고 품질) → 없으면 중앙 박스 폴백.
업그레이드 여지: `pip install rembg`(자동 사용) 또는 opencv GrabCut/사람분할 모델(이 하니스로 검증)."""
import numpy as np
from PIL import Image


def _dominant(g01):
    h, _ = np.histogram(g01.ravel(), bins=32, range=(0, 1))
    return (int(h.argmax()) + 0.5) / 32.0, float(h.max() / h.sum())


def _paper_mask(g01):
    """밝은 종이보다 어두운 자국 = 그림. (largest-CC 필터는 cv2 필요 → 생략; 자국 전체로 충분)"""
    mode, _ = _dominant(g01)
    return g01 < (mode - 0.06)


def _center_box(shape, fx=0.12, fy=0.08, fw=0.76, fh=0.84):
    H, W = shape
    m = np.zeros((H, W), bool)
    m[int(fy * H):int((fy + fh) * H), int(fx * W):int((fx + fw) * W)] = True
    return m


def _center_salient(g01):
    """모델 없는 폴백: 중앙 박스 ∩ (배경 톤에서 벗어난 픽셀). 흉상은 보통 중앙에 오고,
    박스 안에 섞인 배경(톤=mode)을 빼야 인물 명도폭을 안 희석한다(margin 0.06: recall 유지·오탐 억제)."""
    mode, _ = _dominant(g01)
    return _center_box(g01.shape) & (np.abs(g01 - mode) > 0.06)


def _rembg_mask(pil):
    from rembg import remove                       # 설치돼 있을 때만(없으면 ImportError → 폴백)
    a = np.asarray(remove(pil.convert("RGB")))[..., 3]
    return a > 128


def subject_mask(pil, method="auto"):
    """피사체 영역 불리언 마스크. auto: 밝은 종이면 paper, 아니면 salient(rembg→중앙박스)."""
    g = np.asarray(pil.convert("L"), float) / 255
    if method == "auto":
        mode, frac = _dominant(g)
        method = "paper" if (mode > 0.60 and frac > 0.25) else "salient"
    if method == "paper":
        return _paper_mask(g)
    if method in ("salient", "rembg"):
        try:
            return _rembg_mask(pil)
        except Exception:
            if method == "rembg":
                raise
            return _center_salient(g)
    if method == "center":
        return _center_salient(g)
    raise ValueError(method)


def region_signals_from_mask(pil, mask):
    """region_signals(diagnose.py)와 *동일 계약* — pose 대신 주어진 mask 사용.
    image_signals 결과에 update 하면 s_value_structure 의 figure 경로가 그대로 작동."""
    if mask is None:
        return {}
    g = np.asarray(pil.convert("L"), float) / 255
    if mask.sum() < 50 or (~mask).sum() < 50:
        return {}
    fig, bg = g[mask], g[~mask]
    lo, hi = np.percentile(fig, [10, 90])
    return {"figure_value_range": float(hi - lo),
            "figure_bg_contrast": float(abs(fig.mean() - bg.mean()))}
