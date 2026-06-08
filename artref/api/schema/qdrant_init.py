from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from config import settings

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
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),  # ViT-B/32 = 512
        )
        print("collection created:", settings.qdrant_collection)
    else:
        print("collection exists:", settings.qdrant_collection)

    # 필터(body_type/gender/region/category 등)를 효율화. 이미 있으면 건너뜀.
    for field, schema in INDEX_FIELDS.items():
        try:
            c.create_payload_index(settings.qdrant_collection,
                                   field_name=field, field_schema=schema)
            print("payload index:", field)
        except Exception as e:
            print(f"payload index {field} skip: {type(e).__name__}")


if __name__ == "__main__":
    init()
