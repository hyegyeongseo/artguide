"""DB-중립 벡터 export(Parquet) → 같은 embedding_model 이전 시 재임베딩 없이 bulk load."""
import io, sys
import pyarrow as pa, pyarrow.parquet as pq
sys.path.insert(0, "api")
from stores import vectors as vstore
from stores.s3 import s3
from config import settings

def export(date):
    rows = list(vstore.iter_all(with_vectors=True))
    tbl = pa.table({"ref_id": [r[0] for r in rows],
                    "embedding": [r[1] for r in rows],
                    "payload": [str(r[2]) for r in rows]})
    buf = io.BytesIO(); pq.write_table(tbl, buf)
    s3.put_object(Bucket=settings.s3_bucket, Key=f"exports/vectors_{date}.parquet",
                  Body=buf.getvalue())
    print("exported", len(rows), "vectors")

if __name__ == "__main__":
    export(sys.argv[1] if len(sys.argv) > 1 else "latest")
