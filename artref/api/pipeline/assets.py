"""Grounded guide-asset 선택 — 각 관찰(블록)에 붙일 '설명 자료'를 후보 중에서 고른다.

레퍼런스(실제 참고작) 선택과 *같은 그라운딩 패턴*의 '자료 채널 하나 더'다. 불변식은 agent.py와 동형:
  • 룰이 소유 : 축별 자료 후보 집합(미리 적재된 ai_example·backbone_3d + 축마다 *항상* 생성 가능한 svg 도식 바닥).
  • 정책이 소유 : 그 후보 *안에서의* type 선택(축별 선호 순서 + 적용가능성).
  • 절대 못 함  : 후보 밖 자료를 지어내기 / 측정 안 한 축에 자료를 '참고작'인 양 붙이기.

안전 속성 두 가지(둘 다 그라운딩 서사를 지킨다):
  1) svg 도식은 축마다 *항상* 만들 수 있는 바닥 → 슬롯이 비거나 환각될 일이 없다(레퍼런스의 degraded 폴백과 동형).
  2) 해부·손·비율처럼 AI가 자주 틀리는 축에는 ai_example을 *후보에서 제외* → 초보자에게 잘못된 형태를 권하지 않는다.

한 번에 자료는 *하나만*(type 라벨 동봉). UI는 type을 보고 렌더만 바꾸고, 'type 스왑'으로 다른 후보를 보여줄 수 있다.
스키마로는 GuideBlock/NextSteps 에 guide_asset:{type,ref_id,label,caption} 한 필드가 추가될 뿐 — 새 파이프라인이 아니다.
"""
from pipeline.profiles import POSE_DEPENDENT

SVG = "svg"
AI = "ai_example"
BACKBONE = "backbone_3d"

# 사용자에게 '무엇을 보고 있는지' 알려 신뢰 서사를 보호하는 라벨(결정적 도해 / 기하 참고 / AI 일러스트).
TYPE_LABEL = {SVG: "도식", AI: "AI 예시", BACKBONE: "3D 참고"}

# 축별 선호 순서(적재된 *비-바닥* type 중에서 고를 우선순위). 어느 것도 없으면 svg 도식 바닥으로 떨어진다.
#   - 단축·무게·관절·비율(입체/기하가 핵심) : 3D 백본이 가장 신뢰. 그 다음 svg 도식.
#   - 명암·구도(방법이 명확)               : svg 방법 도해 우선, 없으면 AI 느낌 예시.
#   - 빛 방향·색(느낌이 핵심)              : AI 일러스트가 강함, 없으면 svg.
#   - 손(AI가 가장 자주 틀림)              : svg 도식만(AI·확신형 3D 배제).
AXIS_PREF = {
    "foreshortening":      [BACKBONE, SVG],
    "weight_balance":      [BACKBONE, SVG],
    "joint_articulation":  [BACKBONE, SVG],
    "proportion":          [BACKBONE, SVG],
    "action_line":         [BACKBONE, SVG],
    "hand_structure":      [SVG],
    "value_structure":     [SVG, AI],
    "composition_balance": [SVG, AI],
    "light_direction":     [AI, SVG],
    "color_harmony":       [AI, SVG],
    # 풍경 전용 축: 원근/지평선은 svg 도해, 대기원근·깊이는 AI 일러스트가 느낌을 잘 보여줌.
    "linear_perspective":      [SVG],
    "horizon_placement":       [SVG],
    "atmospheric_perspective": [AI, SVG],
    "depth_layering":          [SVG, AI],
}
_DEFAULT_PREF = [SVG]   # 모르는 축도 svg 바닥으로 안전하게 동작

# AI가 형태를 자주 틀리는 축 — ai_example을 *후보에서 제외*한다(있어도 안 붙임). 해부·손·비율.
AI_AVOID = {"hand_structure", "joint_articulation", "foreshortening", "proportion", "weight_balance"}

# 축마다 항상 가능한 svg 도식 바닥의 설명(방법/도해). 없는 축은 일반 격자 도해로 폴백.
_FLOOR_CAPTION = {
    "weight_balance":      "골반 중심에서 바닥으로 수직선을 하나 그어보세요 — 두 발 사이를 지나가면 안정적으로 읽혀요.",
    "hand_structure":      "손을 손바닥 덩어리 + 손가락으로 먼저 단순화해보세요 — 큰 덩어리가 맞으면 디테일이 자연스러워져요.",
    "joint_articulation":  "관절을 원, 뼈를 선으로 먼저 잡아보세요 — 꺾이는 방향이 분명해지면 포즈가 살아나요.",
    "value_structure":     "명암을 밝음·중간·어둠 3단계로 묶어 보는 도식이에요.",
    "composition_balance": "화면을 3분할해 무게가 어디로 쏠리는지 보는 썸네일 격자예요.",
    "proportion":          "머리 하나를 단위로 등신을 재는 비율 사다리예요.",
    "foreshortening":      "면이 시점으로 줄어드는 정도를 보는 투시 격자예요.",
    "action_line":         "포즈를 관통하는 하나의 큰 흐름(동세 선)을 보는 도식이에요.",
    "light_direction":     "광원 한 개에서 면이 받는 빛의 방향을 보는 도식이에요.",
    "color_harmony":       "색상환에서 쓰는 색들의 관계를 보는 도식이에요.",
    "linear_perspective":      "선들이 한 소실점으로 모이는 원근 격자 도식이에요.",
    "horizon_placement":       "지평선을 화면 위·아래 1/3에 두는 배치 도식이에요.",
    "atmospheric_perspective": "거리에 따라 대비·채도가 옅어지는 깊이 도식이에요.",
    "depth_layering":          "근·중·원경 세 층으로 공간을 나눠 보는 도식이에요.",
}
_GENERIC_CAPTION = "이 부분을 어떻게 나눠 보는지 도해로 정리한 예시예요."


def floor_asset(sp):
    """축마다 항상 존재하는 svg 도식 바닥(슬롯이 절대 비지 않게 하는 폴백)."""
    return {"type": SVG, "ref_id": f"floor:{sp}", "label": TYPE_LABEL[SVG],
            "caption": _FLOOR_CAPTION.get(sp, _GENERIC_CAPTION)}


# 축별 항상-가능한 도식 SVG(서빙용). 적재 자료가 0개여도 슬롯이 실제 그림을 가진다는 보증.
_INK, _SUB = "#3a3a3a", "#9aa0a6"
_FLOOR_SVG = {
    "value_structure":
        '<rect x="20" y="40" width="60" height="80" fill="#f2f2f2" stroke="{i}"/>'
        '<rect x="80" y="40" width="60" height="80" fill="#9a9a9a" stroke="{i}"/>'
        '<rect x="140" y="40" width="60" height="80" fill="#2b2b2b" stroke="{i}"/>'
        '<text x="110" y="150" text-anchor="middle" fill="{s}" font-size="13">밝음 · 중간 · 어둠</text>',
    "composition_balance":
        '<rect x="30" y="30" width="180" height="120" fill="none" stroke="{i}"/>'
        '<line x1="90" y1="30" x2="90" y2="150" stroke="{s}" stroke-dasharray="4"/>'
        '<line x1="150" y1="30" x2="150" y2="150" stroke="{s}" stroke-dasharray="4"/>'
        '<line x1="30" y1="70" x2="210" y2="70" stroke="{s}" stroke-dasharray="4"/>'
        '<line x1="30" y1="110" x2="210" y2="110" stroke="{s}" stroke-dasharray="4"/>'
        '<circle cx="150" cy="70" r="6" fill="{i}"/>',
    "proportion":
        ''.join(f'<line x1="60" y1="{30+i*16}" x2="160" y2="{30+i*16}" stroke="{{s}}"/>' for i in range(8))
        + '<line x1="60" y1="30" x2="60" y2="158" stroke="{i}"/>'
        + '<line x1="160" y1="30" x2="160" y2="158" stroke="{i}"/>'
        + '<text x="170" y="36" fill="{s}" font-size="11">1</text>'
        + '<text x="170" y="156" fill="{s}" font-size="11">8</text>',
    "foreshortening":
        '<polygon points="40,40 200,60 200,120 40,140" fill="none" stroke="{i}"/>'
        + ''.join(f'<line x1="{40+i*40}" y1="{40+i*5}" x2="{40+i*40}" y2="{140-i*5}" stroke="{{s}}"/>' for i in range(1,4)),
}
_GENERIC_SVG = ('<rect x="40" y="40" width="160" height="100" fill="none" stroke="{i}"/>'
                '<line x1="40" y1="90" x2="200" y2="90" stroke="{s}" stroke-dasharray="4"/>'
                '<line x1="120" y1="40" x2="120" y2="140" stroke="{s}" stroke-dasharray="4"/>')


def floor_svg(sp):
    """그 축의 도식 SVG 문자열(라우트가 그대로 서빙). 어떤 축도 최소한 일반 격자 도해는 항상 나온다."""
    body = _FLOOR_SVG.get(sp, _GENERIC_SVG).format(i=_INK, s=_SUB)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 180" '
            f'width="240" height="180" role="img">{body}</svg>')


def gather_candidates(sp, loaded=None, degraded=False):
    """이 sub_problem의 자료 후보를 모은다 = (적재 자료 ∩ 안전 규칙) + svg 도식 바닥.

    loaded: 미리 적재·인덱싱된 자료 dict 리스트([{type, ref_id, label?, caption?}, ...]) 또는 None(아직 없음).
      안전 규칙으로 거른다:
        • AI_AVOID 축의 ai_example 은 제외(잘못된 형태 권유 방지).
        • degraded(전신 미검출) + 포즈 의존 축의 backbone_3d 는 제외(측정 못 한 전신 포즈를 확신형으로 보여주지 않음).
      바닥(svg 도식)은 항상 마지막 후보로 포함 → 후보가 비는 일이 없다.
    """
    out = []
    for a in (loaded or []):
        t = a.get("type")
        if t == AI and sp in AI_AVOID:
            continue
        if t == BACKBONE and degraded and sp in POSE_DEPENDENT:
            continue
        if t not in (SVG, AI, BACKBONE):
            continue
        out.append({"type": t, "ref_id": a["ref_id"],
                    "label": a.get("label") or TYPE_LABEL[t],
                    "caption": a.get("caption", "")})
    out.append(floor_asset(sp))      # 바닥은 항상 후보(마지막)
    return out


def select_for(sp, candidates):
    """축별 선호 순서대로, 적재된(=바닥 아님) type을 먼저 고른다. 선호 type이 적재돼 있지 않으면 svg 도식 바닥.

    바닥은 '마지막 수단'이라 적재 후보보다 절대 앞서지 않는다(svg가 선호 1순위여도, 적재 svg가 없으면
    AI 같은 다음 선호를 먼저 시도한 뒤에야 바닥으로 떨어진다 → 느낌 예시가 영영 안 뜨는 일이 없음).
    """
    if not candidates:
        return floor_asset(sp)
    loaded_by_type = {}
    floor = None
    for c in candidates:
        if c["ref_id"].startswith("floor:"):
            floor = c
        else:
            loaded_by_type.setdefault(c["type"], c)
    for t in AXIS_PREF.get(sp, _DEFAULT_PREF):
        if t in loaded_by_type:
            return loaded_by_type[t]
    return floor or floor_asset(sp)


def validate(asset, candidates):
    """grounding 강제 — 고른 자료가 후보 집합 안에 있어야 한다(ref_id 기준). 아니면 None(→ 바닥 폴백)."""
    if not asset:
        return None
    allowed = {c["ref_id"] for c in candidates}
    return asset if asset.get("ref_id") in allowed else None


def pick(sp, loaded=None, degraded=False):
    """한 축에 대해 후보 조립 → 선택 → 검증 → (실패 시) 바닥. 항상 grounded 한 자료 하나를 반환."""
    cands = gather_candidates(sp, loaded=loaded, degraded=degraded)
    chosen = validate(select_for(sp, cands), cands)
    return chosen or floor_asset(sp)


def attach(blocks, degraded=False, index=None):
    """코치 블록 각각에 guide_asset 하나를 결정적으로 붙인다(가드레일 '뒤'에서 — LLM이 못 지어냄).

    index(sp -> 적재 자료 리스트)가 있으면 그걸 후보로, 없으면 svg 도식 바닥만으로 동작한다.
    한 블록당 자료는 *하나*(one-at-a-time). 블록 객체에 .guide_asset 을 직접 세팅한다.
    """
    idx = index or {}
    for b in blocks:
        sp = getattr(b, "sub_problem", None) or (b.get("sub_problem") if isinstance(b, dict) else None)
        if not sp:
            continue
        a = pick(sp, loaded=idx.get(sp), degraded=degraded)
        if isinstance(b, dict):
            b["guide_asset"] = a
        else:
            b.guide_asset = a
    return blocks
