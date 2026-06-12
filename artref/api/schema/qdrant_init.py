import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from config import settings
from ml.embed import embedder   # 실제 임베딩 차원을 모델에서 가져옴(512/768 하드코딩 제거)

# 필터용 payload 인덱스(필드 -> 스키마). 문자열 스키마로 두어 버전 호환.
INDEX_FIELDS = {
    "source_type": "keyword", "commercial_ok": "bool",
    "gender": "keyword", "body_type": "keyword",
    "region": "keyword", "category": "keyword",
}


def init():
    c = QdrantClient(url=settings.qdrant_url)
    if not c.collection_exists(settings.qdrant_collection):
        c.create_collection(
            settings.qdrant_collection,
            # 임베더가 결정하는 실제 차원 사용 (ViT-B/32=512, ViT-L/14=768).
            vectors_config=VectorParams(size=embedder.dim, distance=Distance.COSINE),
        )
        print(f"collection created: {settings.qdrant_collection} (dim={embedder.dim})")
    else:
        print("collection exists:", settings.qdrant_collection)

    for field, schema in INDEX_FIELDS.items():
        try:
            c.create_payload_index(settings.qdrant_collection,
                                   field_name=field, field_schema=schema)
            print("payload index:", field)
        except Exception as e:
            print(f"payload index {field} skip: {type(e).__name__}")


if __name__ == "__main__":
    init()
