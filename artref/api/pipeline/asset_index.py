"""pipeline/asset_index.py — self_render(3D 백본) 렌더를 guide_asset 'backbone_3d' 후보로 색인.

레퍼런스 채널(search.py, 의미검색+self_render 부스트)과는 *별개*의 다리다. 여기서 만든 색인은
pipeline/coach.py 가 가드레일 뒤에서 블록·집중 축에 붙이는 guide_asset 슬롯의 backbone_3d 후보가 된다.

설계:
  • 룰이 소유 : 어떤 렌더가 어느 축(sub_problem)에 쓸모 있는지(클립 키워드 + 뷰 각도 휴리스틱).
  • 정책이 소유 : assets.py 의 축별 선호(단축·무게·관절·비율·동세는 backbone_3d 1순위).
  • 절대 못 함  : 없는 렌더를 지어내기. DB/self_render 가 비면 빈 색인 → assets 가 svg 도식 바닥으로 폴백.

축 매핑은 *적재된 render_params(clip/azimuth/elevation) + region* 만으로 결정한다 → 재렌더 불필요.
전신(region='full') 렌더만 본다(손·발·머리 크롭은 레퍼런스 슬롯의 region 필터로 가고, 손 축의
guide_asset 은 assets.py 에서 svg 도식만 쓰므로 여기서 backbone 을 달지 않는다).

비용: self_render 행을 한 번 색인해 메모리 캐시(행 수가 바뀌면 자동 갱신) → /guide 당 추가비용 ~0.
"""
import json
from collections import defaultdict
import os
import re

BACKBONE = "backbone_3d"
LABEL = "3D 참고"

# 축 ← 클립 이름 키워드. 한 클립이 여러 축에 쓰일 수 있다(예: Reaching Out = 단축 + 관절).
#   backbone 이 1순위인 축(assets.AXIS_PREF)만 둔다 — 손·명암·구도·빛·색은 여기서 다루지 않음.
_AXIS_KEYWORDS = {
    "foreshortening":     ("reach", "point", "throw", "pick", "punch", "kick", "aim", "lunge"),
    "weight_balance":     ("walk", "run", "catwalk", "crouch", "lunge", "step", "lean",
                           "pick", "balance", "march"),
    "joint_articulation": ("sit", "crouch", "kneel", "pick", "throw", "reach", "bend",
                           "climb", "lean"),
    "action_line":        ("throw", "kick", "punch", "run", "jump", "dance", "swing",
                           "sprint", "sword", "spin", "walk"),
    "proportion":         ("idle", "stand", "breath", "neutral", "tpose", "apose",
                           "rest", "wait"),
}
BACKBONE_AXES = tuple(_AXIS_KEYWORDS)   # 이 축들에만 backbone 후보가 붙는다

_AXIS_CAPTION = {
    "foreshortening":     "사지가 시점으로 줄어드는 단축을 3D 형태로 본 참고예요.",
    "weight_balance":     "체중이 어느 발로 쏠리는지 3D 형태로 본 참고예요.",
    "joint_articulation": "관절이 굽는 방향과 각도를 3D 형태로 본 참고예요.",
    "proportion":         "전신 비율을 3D 형태로 본 기준 참고예요.",
    "action_line":        "포즈를 관통하는 큰 흐름(동세)을 3D 형태로 본 참고예요.",
}
_THREE_QUARTER = {45, 135, 225, 315}    # 3/4 뷰 — 입체가 가장 잘 읽힘


def axes_for_clip(clip):
    """클립 이름 → 이 클립이 쓸모 있는 축 집합(키워드 매칭). region='full' 렌더에만 적용."""
    c = (clip or "").lower()
    return {sp for sp, kws in _AXIS_KEYWORDS.items() if any(k in c for k in kws)}


def _view_rank(sp, az, el):
    """한 축에서 '먼저 보여줄' 뷰 정렬 키(작을수록 먼저). guide_asset 은 하나만 띄우므로 가장 illustrative한 뷰를 앞으로.

    - foreshortening : 고도 높을수록(단축 강조) + 3/4 뷰 우선.
    - proportion     : 정면(az0) + 낮은 고도(왜곡 적은 기준컷) 우선.
    - 그 외          : 3/4 뷰 우선.
    """
    az = az if az is not None else 0
    el = el if el is not None else 12
    if sp == "foreshortening":
        return (-(el), 0 if az in _THREE_QUARTER else 1, az)
    if sp == "proportion":
        return (0 if az == 0 else 1, el, az)
    return (0 if az in _THREE_QUARTER else 1, az, el)


def _candidates_from_rows(rows):
    """self_render 행 [(ref_id, region, category, render_params)] → {sub_problem: [asset, ...]}.

    render_params 는 dict 또는 JSON 문자열 모두 허용(드라이버에 따라 다름).
    """
    by_axis = defaultdict(list)
    for ref_id, region, _category, rp in rows:
        if region and region != "full":
            continue                              # 크롭은 레퍼런스 슬롯으로
        if isinstance(rp, str):
            try:
                rp = json.loads(rp)
            except Exception:
                rp = {}
        rp = rp or {}
        clip, az, el = rp.get("clip"), rp.get("azimuth"), rp.get("elevation")
        for sp in axes_for_clip(clip):
            by_axis[sp].append((_view_rank(sp, az, el), ref_id))
    out = {}
    for sp, items in by_axis.items():
        items.sort(key=lambda t: t[0])
        seen, ordered = set(), []
        for _, rid in items:
            if rid not in seen:
                seen.add(rid)
                ordered.append(rid)
        out[sp] = [{"type": BACKBONE, "ref_id": rid, "label": LABEL,
                    "caption": _AXIS_CAPTION.get(sp, "")} for rid in ordered]
    return out


_CACHE = {"count": -1, "index": {}}
# reference 도식(파일 기반 svg 자료): manifest.json 의 asset_index + 안전한 파일 서빙.
_REF = {"dir": None, "index": None}
_AI = {"index": None}                              # ai_example(생성형) guide_asset 후보 캐시
_REF_NAME_RE = re.compile(r"^[a-z0-9_]+\.svg$")   # 경로탈출·임의경로 차단


def clear_cache():
    _CACHE["count"], _CACHE["index"] = -1, {}
    _REF["dir"], _REF["index"] = None, None
    _AI["index"] = None


def _reference_dir():
    """reference/*.svg + manifest.json 이 있는 디렉터리 해석(캐시). env > docker 마운트 > 소스 상대경로."""
    if _REF["dir"] is not None:
        return _REF["dir"]
    here = os.path.dirname(__file__)                       # .../artref/api/pipeline
    cands = [os.environ.get("REFERENCE_DIR"),
             "/repo/assets/reference",                      # docker: ./:/repo:ro 마운트
             os.path.join(here, "..", "..", "assets", "reference"),       # 소스: artref/assets/reference
             os.path.join(here, "..", "..", "..", "woz", "public", "reference")]  # repo/woz/public/reference
    for d in cands:                                         # manifest 있는 곳 우선
        if d and os.path.isfile(os.path.join(d, "manifest.json")):
            _REF["dir"] = os.path.abspath(d)
            return _REF["dir"]
    for d in cands:                                         # 없으면 svg만 있는 디렉터리라도
        if d and os.path.isdir(d):
            _REF["dir"] = os.path.abspath(d)
            return _REF["dir"]
    _REF["dir"] = ""                                        # 못 찾음
    return _REF["dir"]


def _load_reference_index():
    """assets/reference/manifest.json 의 asset_index → {sub_problem: [{type:'svg', ref_id, label, caption}]}.

    파일/매니페스트 없으면 빈 색인(서비스는 정상, svg 도식 바닥으로 폴백). personas 등 여분 키는 버린다.
    """
    if _REF["index"] is not None:
        return _REF["index"]
    idx = {}
    d = _reference_dir()
    if d:
        try:
            ai = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8")).get("asset_index", {})
            for sp, cands in ai.items():
                idx[sp] = [{"type": c.get("type", "svg"), "ref_id": c["ref_id"],
                            "label": c.get("label", "도식"), "caption": c.get("caption", "")}
                           for c in cands if c.get("ref_id")]
        except Exception as e:
            print(f"[asset_index] reference manifest 로드 실패(무시): {type(e).__name__}: {e}")
    _REF["index"] = idx
    return idx


def read_reference_svg(ref_id):
    """ref_id 'reference/<name>.svg' → svg 문자열(없거나 경로탈출이면 None). main.py 라우트가 서빙용으로 호출."""
    if not ref_id.startswith("reference/"):
        return None
    name = os.path.basename(ref_id[len("reference/"):])    # basename → 경로탈출 차단
    if not _REF_NAME_RE.match(name):
        return None
    d = _reference_dir()
    if not d:
        return None
    p = os.path.join(d, name)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _load_index():
    """self_render 색인 로드(행 수가 바뀌면 갱신). DB 없거나 비면 빈 색인 → svg 도식 바닥으로 폴백."""
    try:
        from stores.db import engine
        from sqlalchemy import text
        with engine.begin() as cx:
            (cnt,) = cx.execute(text(
                "SELECT COUNT(*) FROM reference_images WHERE source_type='self_render'")).fetchone()
            if cnt == _CACHE["count"]:
                return _CACHE["index"]
            rows = cx.execute(text(
                "SELECT ref_id, region, category, render_params FROM reference_images "
                "WHERE source_type='self_render'")).fetchall()
        _CACHE["index"] = _candidates_from_rows(list(rows))
        _CACHE["count"] = cnt
        return _CACHE["index"]
    except Exception as e:
        print(f"[asset_index] self_render 색인 실패(무시, 빈 색인): {type(e).__name__}: {e}")
        return {}


def _ai_candidates_from_rows(rows):
    """rows: [(ref_id, tags_json)] → {렌더링축: [{type:'ai_example', ref_id, label:'AI 예시', caption}]}.

    tags.supports 의 축에만 매핑하되, AI_AVOID(손·비율·단축·관절·무게)는 *제외*(안전벨트 —
    렌더링 축에만 AI를 붙인다). guide_asset 슬롯에서 assets.AXIS_PREF 가 빛·색에 AI 우선, 명암·구도에 폴백.
    """
    from pipeline.assets import AI_AVOID
    out = defaultdict(list)
    for ref_id, tags_json in rows:
        try:
            tags = json.loads(tags_json) if isinstance(tags_json, str) else (tags_json or {})
        except Exception:
            tags = {}
        cap = tags.get("caption", "")
        for sp in tags.get("supports", []) or []:
            if not sp or sp in AI_AVOID:
                continue
            out[sp].append({"type": "ai_example", "ref_id": ref_id,
                            "label": "AI 예시", "caption": cap})
    return dict(out)


def _load_ai_index():
    """source_type='ai_example' 행을 tags.supports 별로 묶어 guide_asset 후보로. DB 없으면 빈 색인."""
    if _AI["index"] is not None:
        return _AI["index"]
    idx = {}
    try:
        from stores.db import engine
        from sqlalchemy import text
        with engine.begin() as cx:
            rows = cx.execute(text(
                "SELECT ref_id, tags FROM reference_images WHERE source_type='ai_example'")).fetchall()
        idx = _ai_candidates_from_rows([(r[0], r[1]) for r in rows])
    except Exception as e:
        print(f"[asset_index] ai_example 색인 실패(무시, 빈 색인): {type(e).__name__}: {e}")
    _AI["index"] = idx
    return idx


def build_asset_index(sub_problems, limit_per_axis=8):
    """요청된 축들의 guide_asset 후보 색인 = backbone_3d(self_render, DB) + svg 도식(reference, 파일) 병합.

    pipeline/coach.py 가 run_guide(..., asset_index=...) 로 받아 블록·집중 축에 자료를 붙인다. 선택은 assets.AXIS_PREF:
      - 단축·무게·관절·비율·동세 : backbone_3d 우선 → 없으면 reference svg → 없으면 인라인 도식 바닥.
      - 명암·구도·빛·색·손        : reference svg 우선(backbone 없음) → 없으면 인라인 도식 바닥.
    어느 후보도 없으면 assets 가 floor:<축> 인라인 SVG로 폴백(슬롯은 절대 안 빔).
    """
    bb = _load_index()
    ref = _load_reference_index()
    ai = _load_ai_index()
    out = {}
    for sp in {s for s in sub_problems if s}:
        merged = (bb.get(sp, [])[:limit_per_axis]
                  + ref.get(sp, [])[:limit_per_axis]
                  + ai.get(sp, [])[:limit_per_axis])
        if merged:
            out[sp] = merged
    return out
