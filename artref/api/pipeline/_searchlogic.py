"""pipeline/_searchlogic.py — 검색 필터·부스트의 순수 로직(IO 없음 → 단위테스트 용이).

search.py 가 이걸로 (must, must_not) 필터를 만들고 점수를 가산한다.
- 형태 persona(pose/anatomy/hand) 질의엔 ai_example 을 must_not 으로 차단 → AI 해부가 근거 슬롯에 누출되지 않음.
- source_type/persona/medium/track 일치는 *소프트 가산*(하드필터 아님 → 라이브러리가 비면 폴백 유지).
"""
# persona → 우선 source_type (가산 부스트, 하드 아님)
SOURCE_PREF = {"pose": "self_render", "anatomy": "self_render", "hand": "self_render",
               "light": "museum", "color": "museum", "style": "museum", "mood": "museum",
               "composition": "museum", "perspective": "museum"}  # 이미지/풍경 축은 미술관 우선
# AI가 형태를 자주 틀리는 축의 persona — ai_example 을 결과에서 제외(하드)
CONSTRUCTION_PERSONAS = {"pose", "anatomy", "hand"}
SRC_BOOST, PERSONA_BOOST, MEDIUM_BOOST, TRACK_BOOST = 0.06, 0.05, 0.04, 0.04


def build_filters(persona=None, filters=None):
    """(must, must_not) dict 반환. must=commercial_ok + 선택 filters(hard).
    형태 persona면 must_not 에 source_type=ai_example 추가(AI 해부 누출 차단)."""
    must = {"commercial_ok": True}
    for k, v in (filters or {}).items():
        if v is not None and v != "":
            must[k] = v
    must_not = {}
    if persona in CONSTRUCTION_PERSONAS:
        must_not["source_type"] = "ai_example"
    return must, must_not


def boost(meta, persona=None, medium=None, track=None):
    """소프트 가산점: 우선 source_type / persona 일치 / 사용자 medium·track 일치.
    medium·track 은 '취향 매칭'이라 가산만(근거 아님)."""
    meta = meta or {}
    s = 0.0
    pref = SOURCE_PREF.get(persona)
    if pref and meta.get("source_type") == pref:
        s += SRC_BOOST
    if persona and persona in (meta.get("personas") or []):
        s += PERSONA_BOOST
    if medium and meta.get("medium") == medium:
        s += MEDIUM_BOOST
    if track and meta.get("track") == track:
        s += TRACK_BOOST
    return s
