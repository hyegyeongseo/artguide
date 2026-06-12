"""stores/_vecfilter.py — Pinecone metadata 필터 변환(순수 함수, 의존성 없음 → 단위테스트 용이).

Qdrant Filter(must/must_not)에 대응하는 Pinecone mongo식 필터 dict를 만든다.
  must     → {key: {"$eq": v}}   (v 가 list/tuple/set 이면 {"$in": [...]})
  must_not → {key: {"$ne": v}}   (v 가 list/tuple/set 이면 {"$nin": [...]})
형태축 ai_example 게이트는 must_not={"source_type": "ai_example"} 로 들어와 {"$ne": "ai_example"} 가 된다.
"""


def pinecone_filter(must=None, must_not=None):
    f = {}
    for k, v in (must or {}).items():
        f[k] = {"$in": list(v)} if isinstance(v, (list, tuple, set)) else {"$eq": v}
    for k, v in (must_not or {}).items():
        f[k] = {"$nin": list(v)} if isinstance(v, (list, tuple, set)) else {"$ne": v}
    return f or None
