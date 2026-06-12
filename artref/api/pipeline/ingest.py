import io, json, uuid
from sqlalchemy import text
from stores.s3 import put_image, put_svg
from stores.db import engine
from stores import vectors as vstore
from ml.embed import embedder
from config import settings


def ingest(pil, *, source_type, license, personas, tags,
           attribution=None, commercial_ok=True, render_params=None,
           payload_extra=None, svg_bytes=None):
    """레퍼런스 1장 적재: S3(PNG[+SVG]) + Qdrant(이미지벡터+payload) + MySQL(메타).

    payload_extra 의 region/category/body_type/gender 는 Qdrant 필터 + MySQL 컬럼 양쪽에
    저장한다(MySQL에도 있어야 S3→재임베딩 재구축이 무손실 — 002 마이그레이션 필요).
    svg_bytes 가 주어지면 svg/{ref_id}.svg 로 저장하고 svg_key 를 채운다(Phase 4 구축선).
    """
    ref_id = str(uuid.uuid4())
    buf = io.BytesIO(); pil.save(buf, "PNG")
    image_key = f"images/{ref_id}.png"
    put_image(image_key, buf.getvalue())

    svg_key = None
    if svg_bytes:
        svg_key = f"svg/{ref_id}.svg"
        put_svg(svg_key, svg_bytes)

    vec = embedder.image(pil)
    payload = {"source_type": source_type, "commercial_ok": commercial_ok, "personas": personas}
    px = {k: v for k, v in (payload_extra or {}).items() if v is not None}
    payload.update(px)  # body_type/gender/region/category 등 필터용
    vstore.upsert(ref_id, vec.tolist(), payload)   # 백엔드 중립(어댑터) — qdrant/pinecone 무관

    with engine.begin() as cx:
        cx.execute(text("""INSERT INTO reference_images
          (ref_id,image_key,thumb_key,svg_key,source_type,license,attribution,commercial_ok,
           personas,tags,embedding_model,width,height,render_params,
           region,category,body_type,gender)
          VALUES (:r,:k,:tk,:sk,:st,:lic,:at,:ok,:p,:t,:em,:w,:h,:rp,:rg,:cat,:bt,:gd)"""),
          dict(r=ref_id, k=image_key, tk=None, sk=svg_key, st=source_type, lic=license,
               at=attribution, ok=commercial_ok, p=json.dumps(personas),
               t=json.dumps(tags), em=embedder.model_id, w=pil.width, h=pil.height,
               rp=json.dumps(render_params) if render_params else None,
               rg=px.get("region"), cat=px.get("category"),
               bt=px.get("body_type"), gd=px.get("gender")))
    return ref_id
