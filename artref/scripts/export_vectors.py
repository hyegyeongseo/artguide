"""DB-중립 벡터 export(Parquet) → 같은 embedding_model 이전 시 재임베딩 없이 bulk load."""
import io, sys
import pyarrow as pa, pyarrow.parquet as pq
sys.path.insert(0, "api")
from stores.vectors import qc
from stores.s3 import s3
from config import settings

def export(date):
    pts, _ = qc.scroll(settings.qdrant_collection, with_vectors=True, limit=10000)
    tbl = pa.table({"ref_id": [p.id for p in pts],
                    "embedding": [p.vector for p in pts],
                    "payload": [str(p.payload) for p in pts]})
    buf = io.BytesIO(); pq.write_table(tbl, buf)
    s3.put_object(Bucket=settings.s3_bucket, Key=f"exports/vectors_{date}.parquet",
                  Body=buf.getvalue())
    print("exported", len(pts), "vectors")

if __name__ == "__main__":
    export(sys.argv[1] if len(sys.argv) > 1 else "latest")
