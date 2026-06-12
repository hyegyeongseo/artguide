"""track(목표·스타일) 프로파일 — 범용 엔진 위에 갈아끼우는 한 덩어리.

한 프로파일이 세 가지를 묶는다:
  (a) subproblems : 이 track에서 '켜는' 항목(게이팅). 풍경엔 포즈/해부 항목 제외.
  (b) curriculum  : 성장 순서. 인물·풍경이 다름(전역 단일 순서의 한계를 푸는 핵심).
  (c) norms       : 측정 norm. 비율 스코어러의 leg_torso 밴드 등 — 스타일마다 다름.

엔진(diagnose·roadmap)은 이 프로파일만 받아 동작이 달라진다.
상태머신(new→steady)·recurring·tries는 track과 무관하게 공통으로 재사용된다.

명시 track이 오면 그걸 쓰고, 없으면 scene(인물 유무)으로 자동 선택한다.
존재하지 않는 track 문자열은 안전하게 auto로 떨어진다(앱 안 깨짐).

※ 풍경 전용 항목(선원근·대기원근·깊이층·지평선)이 taxonomy에 추가되어 풍경 track 이 이를 순서화한다.
  측정 가능한 둘(대기원근·지평선)은 image 신호 스코어러가 붙고, 나머지 둘은 persona/언급으로 surface.
  스타일별 레퍼런스 렌더(애니/치비 등신)는 3D 백본(MakeHuman 파라미터)에서 생성하는 오프라인 자산 과제.
"""

# 인물 track 기본 순서(구조 먼저). 전체 taxonomy를 커리큘럼으로 사용.
_FIGURE_ORDER = [
    "proportion", "weight_balance", "action_line", "joint_articulation",
    "foreshortening", "hand_structure", "value_structure", "light_direction",
    "composition_balance", "color_harmony",
]
# 비인물(풍경·정물): 풍경 전용 축(원근·대기원근·깊이·지평선) + 범용 축. 구조(구도·원근) 먼저 → 빛/색.
_SCENE_ORDER = ["composition_balance", "horizon_placement", "linear_perspective",
                "atmospheric_perspective", "depth_layering",
                "value_structure", "light_direction", "color_harmony"]

# 단일 출처(SSOT): 커리큘럼/축 정의는 여기 한 곳. roadmap 등 다른 모듈은 이 공개 별칭을 끌어다 쓴다
# (예전엔 roadmap.py 가 _FIGURE_ORDER 를 복제해 drift 위험이 있었음 → 제거).
FIGURE_ORDER = _FIGURE_ORDER
SCENE_ORDER = _SCENE_ORDER
ALL_AXES = _FIGURE_ORDER + [a for a in _SCENE_ORDER if a not in _FIGURE_ORDER]  # 순서 보존 합집합(14축)

# 포즈(전신 키포인트)에 의존하는 축. 포즈가 degraded(전신 미검출)면 측정 불가라,
# 진단·중재에서 이 축들을 '리드(이번에 딱 하나)'로 단정·승격하지 않는다(흉상·초상에 전신 비율 오발화 방지).
# 이미지 기반 축(value_structure·composition_balance·light_direction·color_harmony)은 포즈 없이도 측정된다.
POSE_DEPENDENT = {"proportion", "weight_balance", "foreshortening",
                  "joint_articulation", "action_line", "hand_structure"}

# norms — 비율 스코어러의 leg_torso 밴드(이 밖이면 발화). 대략값, 데이터로 재튜닝 대상.
#   밴드가 None이면 비율 자동 발화를 끈다(스타일을 모를 때 '비율 틀림' 오발화 방지 = 안전 기본값).
_NORM_REAL = {"leg_torso": (0.75, 1.7)}     # 사실체(약 7~8등신)
_NORM_ANIME = {"leg_torso": (0.9, 2.3)}     # 애니/웹툰(다리 길게)
_NORM_CHIBI = {"leg_torso": (0.4, 1.1)}     # 치비/SD(다리 짧게·머리 크게)
_NORM_OFF = {"leg_torso": None}             # 스타일 미상/비인물 → 비율 자동 발화 끔

PROFILES = {
    "realistic_figure": {"label": "사실체 인물", "subproblems": _FIGURE_ORDER,
                         "curriculum": _FIGURE_ORDER, "norms": _NORM_REAL},
    "anime_figure":     {"label": "애니/웹툰 인물", "subproblems": _FIGURE_ORDER,
                         "curriculum": _FIGURE_ORDER, "norms": _NORM_ANIME},
    "chibi_figure":     {"label": "치비/SD", "subproblems": _FIGURE_ORDER,
                         "curriculum": _FIGURE_ORDER, "norms": _NORM_CHIBI},
    "landscape":        {"label": "풍경/정물", "subproblems": _SCENE_ORDER,
                         "curriculum": _SCENE_ORDER, "norms": _NORM_OFF},
}

# 자동(track 미지정) 폴백. 인물이면 인물(자동), 아니면 풍경.
#   인물(자동)은 스타일을 모르므로 norms를 OFF로 둬 비율 오발화를 막는다(사실체 단정 금지).
_FIGURE_AUTO = {"label": "인물(자동)", "subproblems": _FIGURE_ORDER,
                "curriculum": _FIGURE_ORDER, "norms": _NORM_OFF}


def resolve_profile(track=None, scene=None):
    """명시 track 우선 → scene로 자동 → 정보 없으면 기본 레인(인물).

    'scene가 인물 없음'(풍경)과 'scene 자체가 없음'(이미지 없는 /roadmap 호출 등)을 구분한다.
    후자는 주제를 알 수 없으니 제품의 1차 레인인 인물(자동)로 둔다. 알 수 없는 track도 여기로.
    """
    if track and track in PROFILES:
        return PROFILES[track]
    if scene is None:
        return _FIGURE_AUTO                      # 정보 없음 → 기본 레인(인물)
    person = bool(scene.get("subject", {}).get("person", {}).get("present", False))
    return _FIGURE_AUTO if person else PROFILES["landscape"]
