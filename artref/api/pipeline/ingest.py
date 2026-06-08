import io, json, uuid
from sqlalchemy import text
from stores.s3 import put_image
from stores.db import engine
from stores.vectors import qc
from qdrant_client.models import PointStruct
from ml.embed import embedder
from config import settings

def ingest(pil, *, source_type, license, personas, tags,
           attribution=None, commercial_ok=True, render_params=None, payload_extra=None):
    ref_id = str(uuid.uuid4())
    buf = io.BytesIO(); pil.save(buf, "PNG")
    put_image(f"images/{ref_id}.png", buf.getvalue())

    vec = embedder.image(pil)
    payload = {"source_type": source_type, "commercial_ok": commercial_ok, "personas": personas}
    if payload_extra:  # body_type/gender/region/category 등 필터용 필드(None은 제외)
        payload.update({k: v for k, v in payload_extra.items() if v is not None})
    qc.upsert(settings.qdrant_collection,
              points=[PointStruct(id=ref_id, vector=vec.tolist(), payload=payload)])

    with engine.begin() as cx:
        cx.execute(text("""INSERT INTO reference_images
          (ref_id,image_key,source_type,license,attribution,commercial_ok,
           personas,tags,embedding_model,width,height,render_params)
          VALUES (:r,:k,:st,:lic,:at,:ok,:p,:t,:em,:w,:h,:rp)"""),
          dict(r=ref_id, k=f"images/{ref_id}.png", st=source_type, lic=license,
               at=attribution, ok=commercial_ok, p=json.dumps(personas),
               t=json.dumps(tags), em=embedder.model_id, w=pil.width, h=pil.height,
               rp=json.dumps(render_params) if render_params else None))
    return ref_id
