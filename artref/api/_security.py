"""_security.py — 작은 보안 헬퍼들(라우트에서 입력 검증·접근통제에 사용).

main.py 를 크게 안 건드리도록 순수 함수만 모았다. README 의 패치가 이 함수들을 호출한다.
  • valid_ref_id : /image·/svg·/guide-asset 의 DB 조회 ref_id 가 UUID 형식인지(임의 키 조회 차단).
  • ADOPT_EVENTS / PRACTICE_ACTIONS + clean_*: 피드백 로그 이벤트 화이트리스트(랭커 오염·잡값 차단).
  • cors_origins : CORS 허용 출처를 env(CORS_ORIGINS)에서. 운영 도메인을 코드 수정 없이 설정.
"""
import os
import re

# uuid4 형식(하이픈 8-4-4-4-12, hex). museum 등은 str(uuid.uuid4()) 로 만든 ref_id.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# 조직형 ref_id(ai_<축>_<매체>_<트랙>_NNN 등). 영숫자·언더스코어·하이픈만 → '/'·'.'·'..' 불가라 키 경로주입 차단.
_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{1,96}$")


def valid_ref_id(s) -> bool:
    """DB 조회용 ref_id 검증. UUID(museum) 또는 안전 슬러그(ai_example/self_render 등). '/'·'.' 불가로 키 주입 차단.
    floor:/reference/ 같은 자료 슬롯 id 는 별도 분기에서 처리."""
    return bool(s) and isinstance(s, str) and bool(_UUID_RE.match(s) or _SLUG_RE.match(s))


# 피드백 이벤트 화이트리스트(feedback.py / record_practice 와 일치).
ADOPT_EVENTS = frozenset({"shown", "clicked", "saved", "liked", "disliked"})
PRACTICE_ACTIONS = frozenset({"seen", "tried", "later"})


def clean_event(event, allowed=ADOPT_EVENTS):
    """허용 이벤트면 그대로, 아니면 None(호출부가 400 등으로 거절)."""
    return event if event in allowed else None


def clamp_confidence(c):
    """confidence 를 [0,1] 로 클램프(범위 밖 잡값 방지). None 은 그대로."""
    if c is None:
        return None
    try:
        c = float(c)
    except Exception:
        return None
    return max(0.0, min(1.0, c))


def cors_origins():
    """CORS 허용 출처 목록. env CORS_ORIGINS(콤마구분) 없으면 로컬 WoZ 기본값."""
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]
