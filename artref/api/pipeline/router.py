"""상황 판단(intake / triage) — 코칭 파이프라인에 넣기 전에 사용자 입력을 먼저 가른다.

결정적·싸게(키워드 포함 검사, LLM 없음). 키워드 목록은 schema/intake.yaml 에서 로드하며,
파일이 없거나 깨져도 아래 _DEFAULTS 로 동작한다(앱이 절대 안 깨지게).

판단 카테고리(→ 반환 mode):
  generate     "그려줘" 류 생성 요청          → redirect  (대신 그려주지 않음)
  not_drawing  scene.analyzable=False          → clarify   (분석할 그림인지 확인)
  offtopic     코칭 요청이 아닌 잡담·범위 밖   → 그림 있으면 coach(관찰-제안 L1), 없으면 clarify
  score        점수·등급·평가 요청            → coach     (평가하지 않고 관찰로; SYSTEM이 평가어 차단)
  coach        그 외(부위 명시 / 모호 / 빈 입력) → coach

부위/축 감지: intake.yaml 의 lexicon(키워드→sub_problem)으로 user_terms 를 만든다.
  - 키워드 있으면: 그 sub_problem 을 최우선 관찰로 surface(사용자가 콕 집은 관심).
  - 키워드 없으면: 빈 set → diagnose 가 자동 신호로 관찰을 제안(L1 "그냥 봐주세요").
persona: 인물이 보이면 [pose, anatomy], 아니면 [composition, light, color].

반환 시그니처는 기존과 동일: (mode, personas, user_terms). mode ∈ {coach, redirect, clarify}.
"""
import os
import re
import yaml
from functools import lru_cache

INTAKE_PATH = os.environ.get(
    "INTAKE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "schema", "intake.yaml"),
)

# intake.yaml 이 없을 때의 내장 기본값(앱이 안 깨지게).
_DEFAULTS = {
    "generate": ["그려줘", "그려주", "그려 줘", "그려달", "그려 달",
                 "만들어줘", "generate", "draw it", "make it"],
    "score": ["몇 점", "몇점", "점수", "등급", "잘 그렸", "잘그렸",
              "못 그렸", "못그렸", "평가해", "평가 좀", "잘했", "합격", "수준이"],
    "offtopic": ["팔릴까", "팔려", "돈이 되", "ai가 그린", "ai로 그린",
                 "인공지능이 그", "안녕", "고마워", "누구야", "넌 누구"],
    "lexicon": {
        "손": "hand_structure", "손가락": "hand_structure", "손목": "hand_structure",
        "구도": "composition_balance", "배치": "composition_balance", "여백": "composition_balance",
        "색": "color_harmony", "색감": "color_harmony", "팔레트": "color_harmony", "채도": "color_harmony",
        "조명": "light_direction", "광원": "light_direction", "빛": "light_direction", "그림자": "light_direction",
        "명암": "value_structure", "명도": "value_structure", "대비": "value_structure",
        "입체": "value_structure", "톤": "value_structure",
        "자세": "weight_balance", "포즈": "weight_balance", "균형": "weight_balance",
        "무게": "weight_balance", "중심": "weight_balance",
        "비율": "proportion", "비례": "proportion",
        "단축": "foreshortening", "원근": "foreshortening",
        "관절": "joint_articulation", "팔꿈치": "joint_articulation", "무릎": "joint_articulation",
        "동세": "action_line", "동작": "action_line", "액션": "action_line",
    },
}


@lru_cache
def intake_config():
    """schema/intake.yaml 로드(없으면 내장 기본값). 키별로 누락 시 기본값으로 보충."""
    cfg = {}
    try:
        with open(INTAKE_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[router] intake.yaml 로드 실패 → 내장 기본값 사용: {type(e).__name__}: {e}")
    return {k: (cfg.get(k) or _DEFAULTS[k]) for k in _DEFAULTS}


def _has(message, words):
    m = (message or "").lower()
    return any(str(w).lower() in m for w in words)


def detect_terms(message):
    """부위/축 키워드 → sub_problem id 집합 (diagnose 의 user_terms).

    한국어는 단어 사이에 공백이 없어 단순 부분문자열은 오탐이 난다(예: '색' ⊂ '어색해요',
    '명도' ⊂ '설명도'). 키워드 바로 앞이 한글 음절이면 다른 단어의 일부로 보고 제외한다
    (앞 경계 규칙). 뒤쪽 결합(색이/색감)은 그대로 매칭 — 보통 같은 관심사라 안전.
    """
    m = message or ""
    lex = intake_config()["lexicon"]
    found = set()
    for kw, sid in lex.items():
        if re.search(r"(?<![가-힣])" + re.escape(str(kw)), m):
            found.add(sid)
    return found


def triage(message, scene):
    """상황 판단 결과를 (category, mode) 로 반환(로깅·디버그용). resolve()가 이걸 감싼다."""
    msg = message or ""
    cfg = intake_config()
    if _has(msg, cfg["generate"]):
        return "generate", "redirect"
    if not scene.get("analyzable", False):
        return "not_drawing", "clarify"
    has_term = bool(detect_terms(msg))
    if not has_term and _has(msg, cfg["offtopic"]):
        return "offtopic", "coach"        # 그림은 분석 가능 → 관찰 제안(L1)
    if _has(msg, cfg["score"]):
        return "score", "coach"           # 채점하지 않고 관찰 코칭으로
    return "coach", "coach"


def resolve(message, scene):
    """반환: (mode, personas, user_terms). mode ∈ {coach, redirect, clarify}."""
    category, mode = triage(message, scene)
    if mode != "coach":
        return mode, [], set()

    person = scene.get("subject", {}).get("person", {}).get("present", False)
    personas = ["pose", "anatomy"] if person else ["composition", "light", "color"]

    # offtopic 은 부위 언급이 없으니 빈 user_terms(L1 관찰-제안). 그 외엔 키워드 surface.
    user_terms = set() if category == "offtopic" else detect_terms(message)
    return "coach", personas, user_terms
