"""seed_museum_aic.py — Art Institute of Chicago Open Access(CC0)로 museum 축 보강.

AIC는 공개도메인 작품을 CC0로 제공한다(상업 이용 가능, 별도 허가·크레딧 불필요).
is_public_domain=true 인 것만 적재 → 상업-클린. The Met(seed_museum.py)과 동일하게
source_type="museum"/license="CC0" 로 들어가 같은 검색 코퍼스에 합류한다.

실행: docker compose exec -w /repo api python scripts/seed_museum_aic.py [per_query]
     (per_query 기본 20 → 4 persona × 3 query × 20 ≈ 240장)
"""
import sys, io, time, requests
sys.path.insert(0, "api")
from ml.normalize import normalize
from pipeline.ingest import ingest

AIC = "https://api.artic.edu/api/v1/artworks"
IIIF = "https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg"
UA = {"AIC-User-Agent": "artcoach-seed (contact: you@example.com)"}

# 이미지 축(빛·색·구도·무드) 위주. 포즈/해부는 self_render가 맡으므로 제외.
PERSONA_QUERIES = {
    "composition": (["landscape painting", "still life", "interior scene"],
                    ["composition", "mood"]),
    "light":       (["chiaroscuro", "candlelight night interior", "tenebrism"],
                    ["light", "mood"]),
    "color":       (["impressionist landscape", "fauvism", "still life flowers"],
                    ["color", "mood"]),
    "mood":        (["romantic landscape", "nocturne", "tonalism"],
                    ["mood", "color"]),
}


def _search(query, limit):
    params = {"q": query,
              "query[term][is_public_domain]": "true",
              "fields": "id,title,image_id,artist_display,is_public_domain",
              "limit": min(limit * 4, 100)}
    try:
        return requests.get(f"{AIC}/search", params=params, headers=UA,
                            timeout=30).json().get("data", [])
    except Exception as e:
        print("  search 실패:", repr(e)[:60]); return []


def _seed_query(query, personas, limit):
    n = 0
    for o in _search(query, limit):
        if not o.get("is_public_domain") or not o.get("image_id"):
            continue
        try:
            img = requests.get(IIIF.format(image_id=o["image_id"]),
                               headers=UA, timeout=30).content
            pil = normalize(io.BytesIO(img))
            ingest(pil, source_type="museum", license="CC0",
                   attribution=(o.get("artist_display") or "Art Institute of Chicago (CC0)")[:480],
                   personas=personas,
                   tags={"query": query, "title": o.get("title"), "src": "AIC"},
                   commercial_ok=True)
            n += 1
        except Exception as e:
            print("  skip", o.get("id"), repr(e)[:60])
        time.sleep(0.2)
        if n >= limit:
            break
    print(f"  [{query}] seeded {n} (personas={personas})")
    return n


def main():
    per_query = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    total = 0
    for queries, personas in PERSONA_QUERIES.values():
        for q in queries:
            total += _seed_query(q, personas, per_query)
    print("TOTAL AIC CC0 seeded:", total)


if __name__ == "__main__":
    main()
