"""진짜 artcoach 명암 분석기에 붙는 접점. 두 경로를 둔다:
  analyze_value        : degraded(마스크 없음) = baseline.
  analyze_value_masked : 피사체 마스크로 figure_value_range/figure_bg_contrast 채움 = 개선 후보.
production 코드(diagnose) 는 손대지 않고, 마스크 효과를 *하니스로 먼저 검증*한 뒤 통합한다."""
from pipeline.diagnose import image_signals, s_value_structure
from pipeline.mask import subject_mask, region_signals_from_mask


def analyze_value(pil):
    sig = image_signals(pil)
    out = s_value_structure(sig)
    return {"rr": sig.get("value_range_robust"),
            "fired": out is not None, "confidence": out[0] if out else 0.0}


def analyze_value_masked(pil, method="auto"):
    sig = image_signals(pil)
    sig.update(region_signals_from_mask(pil, subject_mask(pil, method)))   # figure_* 주입
    out = s_value_structure(sig)
    rr = sig.get("figure_value_range", sig.get("value_range_robust"))
    return {"rr": rr, "fired": out is not None, "confidence": out[0] if out else 0.0}
