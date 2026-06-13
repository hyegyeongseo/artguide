"""stores/vectors.py — 벡터 DB 어댑터(백엔드 중립).

ingest/search/관리스크립트는 여기 upsert()/query()/delete_by()/iter_all() 만 호출한다.
백엔드는 config.vector_backend 로 고르고, SDK는 *지연 import*. 교체 시 이 파일 한 곳만 바뀐다.
  - qdrant   : 개발(로컬 도커, API 키 불필요)
  - pinecone : 운영(매니지드 SaaS, api_key/index 필요)
"""
from config import settings
from stores._vecfilter import pinecone_filter
import uuid as _uuid

# Qdrant 포인트 ID는 uint/UUID만 허용(Pinecone는 문자열 OK). 문자열 ref_id → 결정적 UUID로 변환해
# 포인트 ID로 쓰고, ref_id 자체는 payload 에 보존한다(검색·조인은 payload.ref_id 로 동작). 같은 ref_id면 같은 UUID(재적재=덮어쓰기).
def _qid(ref_id):
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, str(ref_id)))

_BACKEND = (getattr(settings, "vector_backend", "qdrant") or "qdrant").lower()
_client = None


class Hit:
    """검색 결과 1건(백엔드 무관): id, score, meta(=Qdrant payload / Pinecone metadata)."""
    __slots__ = ("id", "score", "meta")

    def __init__(self, id, score, meta):
        self.id, self.score, self.meta = id, score, (meta or {})


def _qc():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def _pc():
    global _client
    if _client is None:
        from pinecone import Pinecone
        _client = Pinecone(api_key=settings.pinecone_api_key).Index(settings.pinecone_index)
    return _client


def _ns():
    return (getattr(settings, "pinecone_namespace", "") or None)


def _g(m, key):
    """Pinecone match 접근(객체/딕셔너리 호환)."""
    if isinstance(m, dict):
        return m.get(key)
    return getattr(m, key, None)


def _qdrant_conds(d):
    """{key: value}(value 가 list면 다중매치) → [FieldCondition] | None."""
    from qdrant_client.models import FieldCondition, MatchValue, MatchAny
    out = []
    for key, v in (d or {}).items():
        m = MatchAny(any=list(v)) if isinstance(v, (list, tuple, set)) else MatchValue(value=v)
        out.append(FieldCondition(key=key, match=m))
    return out or None


def upsert(id, vec, meta):
    """벡터 1건 적재. meta = 평면 dict(source_type/personas/medium/track 등)."""
    vec = list(vec)
    if _BACKEND == "pinecone":
        _pc().upsert(vectors=[{"id": str(id), "values": vec, "metadata": meta}], namespace=_ns())
        return
    from qdrant_client.models import PointStruct
    meta = {**(meta or {}), "ref_id": str(id)}   # 검색/조인이 payload.ref_id 로 동작하도록 보존
    _qc().upsert(settings.qdrant_collection,
                 points=[PointStruct(id=_qid(id), vector=vec, payload=meta)])


def query(vec, k, must=None, must_not=None):
    """필터 검색 → [Hit]. must/must_not = {meta_key: value}(value list면 다중매치).
    must 모두 일치(commercial_ok 등), must_not 제외(형태축 ai_example 게이트 등)."""
    vec = list(vec)
    if _BACKEND == "pinecone":
        res = _pc().query(vector=vec, top_k=k, filter=pinecone_filter(must, must_not),
                          include_metadata=True, namespace=_ns())
        matches = res["matches"] if isinstance(res, dict) else res.matches
        return [Hit(_g(m, "id"), _g(m, "score"), _g(m, "metadata")) for m in matches]

    from qdrant_client.models import Filter
    flt = Filter(must=_qdrant_conds(must), must_not=_qdrant_conds(must_not))
    res = _qc().query_points(settings.qdrant_collection, query=vec,
                             query_filter=flt, limit=k, with_payload=True)
    return [Hit((h.payload or {}).get("ref_id", h.id), h.score, h.payload or {}) for h in res.points]


def delete_by(must):
    """must={meta_key: value} 매칭 포인트 삭제(self_render 리셋 등)."""
    if _BACKEND == "pinecone":
        _pc().delete(filter=pinecone_filter(must, None), namespace=_ns())
        return
    from qdrant_client.models import Filter, FilterSelector
    flt = Filter(must=_qdrant_conds(must))
    _qc().delete(settings.qdrant_collection, points_selector=FilterSelector(filter=flt))


def iter_all(with_vectors=True, batch=10000):
    """전체 포인트 순회 → (id, vector, meta) 제너레이터. export/reindex 용(qdrant 전용)."""
    if _BACKEND == "pinecone":
        raise NotImplementedError("iter_all 은 qdrant 전용 — Pinecone는 list/fetch 사용")
    offset = None
    while True:
        pts, offset = _qc().scroll(settings.qdrant_collection, with_vectors=with_vectors,
                                   with_payload=True, limit=batch, offset=offset)
        for p in pts:
            yield ((p.payload or {}).get("ref_id", p.id), getattr(p, "vector", None), p.payload or {})
        if not offset:
            break
