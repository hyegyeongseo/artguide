"""태그→검색어 보조 + miss 로깅. (search_text는 reference_query를 직접 쓰므로 선택적 사용)

miss = 진단 관찰의 reference_query로 검색했는데 좋은 레퍼런스가 안 나온 경우.
이 로그가 render_queue → render_poses 배치의 입력("무엇을 더 렌더할지")이 된다.
DB 작업은 전부 예외를 삼켜 /guide 응답을 절대 막지 않는다.
"""
import json
from sqlalchemy import text
from stores.db import engine

BASE_TERMS = {
    "pose": ["dynamic pose"], "anatomy": ["anatomy reference"],
    "hand": ["hand reference"], "light": ["lighting study"],
    "color": ["color palette"], "composition": ["composition"],
}

def to_search_terms(persona, tags):
    return BASE_TERMS.get(persona, [])

def log_miss(term, context=None):
    """같은 term의 미스는 새 행 대신 count를 올린다(미해결 행 한정).
    miss_log엔 term unique key가 없으므로 UPDATE-or-INSERT로 처리.
    context(sub_problem·persona·top_score 등)는 JSON으로 보존 → render_queue가 사용."""
    ctx_json = json.dumps(context, ensure_ascii=False) if context else None
    try:
        with engine.begin() as cx:
            upd = cx.execute(
                text("UPDATE miss_log SET count = count + 1, "
                     "context = COALESCE(:c, context) "
                     "WHERE term = :t AND resolved = 0"),
                {"t": term, "c": ctx_json})
            if upd.rowcount == 0:
                cx.execute(
                    text("INSERT INTO miss_log (term, context) VALUES (:t, :c)"),
                    {"t": term, "c": ctx_json})
    except Exception as e:
        print(f"[miss] 로깅 실패(무시): {type(e).__name__}: {e}")
