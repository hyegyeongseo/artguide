"""asset_index 다리 스텁 테스트 — DB 없이 순수 매핑 로직만 검증.

확인:
  1) 클립 이름 → 축 매핑(키워드). 한 클립이 여러 축에 걸칠 수 있음.
  2) region!='full'(손/발/머리 크롭)은 backbone 후보에서 제외.
  3) 축별 뷰 정렬: 단축은 높은 고도/3-4 뷰 먼저, 비율은 정면(az0) 먼저.
  4) 후보는 backbone_3d type + '3D 참고' 라벨 + 축 캡션을 갖는다.
  5) assets.gather_candidates 와 맞물려 단축에서 backbone 이 실제로 선택되는지(end-to-end).
실행: artref/api 에서  python -m tests.test_asset_index
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import asset_index as AI
from pipeline import assets as A


def _rp(clip, az, el=12):
    return {"clip": clip, "azimuth": az, "elevation": el}


def t_axes_for_clip():
    assert "foreshortening" in AI.axes_for_clip("Reaching Out")
    assert "joint_articulation" in AI.axes_for_clip("Reaching Out")  # 여러 축
    assert "proportion" in AI.axes_for_clip("Standing Idle")
    assert "action_line" in AI.axes_for_clip("Throw Object")
    assert AI.axes_for_clip("Mystery Clip") == set()                 # 매칭 없으면 빈 집합


def t_full_only():
    rows = [("h1", "hand", "action", _rp("Reaching Out", 0)),     # 크롭 → 제외
            ("f1", "full", "action", _rp("Reaching Out", 45))]
    idx = AI._candidates_from_rows(rows)
    ids = {c["ref_id"] for sp in idx for c in idx[sp]}
    assert "h1" not in ids and "f1" in ids, idx


def t_candidate_shape():
    idx = AI._candidates_from_rows([("r1", "full", "action", _rp("Pointing", 45, 35))])
    c = idx["foreshortening"][0]
    assert c["type"] == "backbone_3d" and c["label"] == "3D 참고" and c["caption"], c


def t_view_order_foreshortening():
    # 같은 클립 두 뷰: el35 가 el12 보다 먼저(단축 강조).
    rows = [("low", "full", "action", _rp("Throw Object", 45, 12)),
            ("high", "full", "action", _rp("Throw Object", 45, 35))]
    idx = AI._candidates_from_rows(rows)
    order = [c["ref_id"] for c in idx["foreshortening"]]
    assert order[0] == "high", order


def t_view_order_proportion():
    # 비율: 정면(az0)이 측면(az90)보다 먼저.
    rows = [("side", "full", "rest", _rp("Idle", 90)),
            ("front", "full", "rest", _rp("Idle", 0))]
    idx = AI._candidates_from_rows(rows)
    order = [c["ref_id"] for c in idx["proportion"]]
    assert order[0] == "front", order


def t_end_to_end_backbone_selected():
    # asset_index 후보를 assets.pick 에 넣으면 단축에서 backbone 이 선택돼야 한다.
    idx = AI._candidates_from_rows([("r1", "full", "action", _rp("Reaching Out", 45, 35))])
    chosen = A.pick("foreshortening", loaded=idx["foreshortening"], degraded=False)
    assert chosen["type"] == "backbone_3d" and chosen["ref_id"] == "r1", chosen
    # degraded(전신 미검출)면 같은 후보라도 backbone 제외 → svg 도식 바닥
    chosen2 = A.pick("foreshortening", loaded=idx["foreshortening"], degraded=True)
    assert chosen2["ref_id"] == "floor:foreshortening", chosen2


# --- reference 도식(파일 기반 svg) 연결 ---
import os as _os
_REF_DIR = _os.path.join(_os.path.dirname(__file__), "..", "..", "assets", "reference")


def _use_real_reference():
    AI.clear_cache()
    _os.environ["REFERENCE_DIR"] = _os.path.abspath(_REF_DIR)


def t_reference_index_loads_and_merges():
    _use_real_reference()
    AI._load_index = lambda: {}                 # backbone 없음 → reference svg 만
    idx = AI.build_asset_index(["foreshortening", "value_structure", "hand_structure"])
    for sp in ("foreshortening", "value_structure", "hand_structure"):
        assert idx.get(sp), f"{sp} 에 reference 후보가 있어야 함"
        assert idx[sp][0]["type"] == "svg" and idx[sp][0]["ref_id"].startswith("reference/"), idx[sp][0]


def t_backbone_then_reference_then_floor():
    _use_real_reference()
    bb = AI._candidates_from_rows([("bb1", "full", "action", _rp("Pointing", 45, 35))])
    AI._load_index = lambda: bb                 # 단축에 backbone 있음
    idx = AI.build_asset_index(["foreshortening", "value_structure"])
    # 단축: backbone 선택(1순위)
    assert A.pick("foreshortening", loaded=idx["foreshortening"])["type"] == "backbone_3d"
    # 단축 degraded: backbone 제외 → reference svg (인라인 floor 아님)
    deg = A.pick("foreshortening", loaded=idx["foreshortening"], degraded=True)
    assert deg["type"] == "svg" and deg["ref_id"].startswith("reference/"), deg
    # 명암(backbone 없음): reference svg 선택
    assert A.pick("value_structure", loaded=idx["value_structure"])["ref_id"].startswith("reference/")


def t_read_reference_svg_path_safety():
    _use_real_reference()
    ai = __import__("json").load(open(_os.path.join(_REF_DIR, "manifest.json"), encoding="utf-8"))["asset_index"]
    sample = ai["foreshortening"][0]["ref_id"]               # 예: reference/perspective_grid.svg
    assert "<svg" in (AI.read_reference_svg(sample) or ""), "정상 ref_id는 svg 반환"
    assert AI.read_reference_svg("reference/../../etc/passwd") is None, "경로탈출 차단"
    assert AI.read_reference_svg("reference/nope.svg") is None, "없는 파일은 None"
    assert AI.read_reference_svg("floor:foo") is None, "reference/ 접두 아니면 None"


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 축매핑·full전용·후보형태·뷰정렬·end-to-end(degraded 폴백 포함)")


if __name__ == "__main__":
    run()
