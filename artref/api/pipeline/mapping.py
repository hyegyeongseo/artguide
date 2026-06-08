"""태그→검색어 보조 + miss 로깅. (search_text는 reference_query를 직접 쓰므로 선택적 사용)"""
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
    with engine.begin() as cx:
        cx.execute(text("INSERT INTO miss_log (term, context) VALUES (:t, :c)"),
                   {"t": term, "c": None})
