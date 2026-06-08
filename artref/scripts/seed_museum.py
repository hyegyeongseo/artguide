"""미술관 CC0(예: The Met) 오픈액세스로 레퍼런스 시드.
isPublicDomain(=CC0)만 적재 → 상업-클린.

persona별 검색어로 카테고리를 고르게 채운다. render_batch(자체 렌더)가
아직 비어 있으므로, 포즈/해부 계열도 미술관 figure study로 '뭐라도' 채워
베타 2의 라이브러리 쏠림(soft lighting/warm tone 편중)을 완화하는 게 목적.

주의:
- hand_structure(손 클로즈업 평면)는 미술관 소장품으로 잘 안 잡힌다 →
  render_batch 또는 운영자 수동 보강 필요(런북 참조). 여기선 best-effort.
- 실제 실행은 사용자 환경(인터넷 + 인프라 기동). Met API 레이트리밋 주의.
"""
import sys, io, time, requests
sys.path.insert(0, "api")
from ml.normalize import normalize
from pipeline.ingest import ingest

MET = "https://collectionapi.metmuseum.org/public/collection/v1"

# persona → (Met 검색어들, 함께 붙일 personas 태그)
PERSONA_QUERIES = {
    "composition": (["landscape painting", "still life composition"],
                    ["composition", "mood"]),
    "light":       (["chiaroscuro", "candlelight painting interior"],
                    ["light", "mood"]),
    "color":       (["impressionist landscape", "still life flowers color"],
                    ["color", "mood"]),
    "mood":        (["romantic landscape", "nocturne night scene"],
                    ["mood", "color"]),
    # 포즈/해부 — render_batch 전까지 미술관 figure study로 임시 보강
    "pose":        (["figure study drawing", "standing figure academic"],
                    ["pose", "anatomy"]),
    "anatomy":     (["academic nude study", "anatomical figure drawing"],
                    ["anatomy", "pose"]),
}


def _seed_query(query, personas, limit):
    ids = (requests.get(f"{MET}/search",
                        params={"q": query, "hasImages": "true"}, timeout=30)
           .json().get("objectIDs") or [])
    n = 0
    for oid in ids[: limit * 4]:
        try:
            o = requests.get(f"{MET}/objects/{oid}", timeout=30).json()
        except Exception:
            continue
        if not o.get("isPublicDomain") or not o.get("primaryImage"):
            continue  # CC0 + 이미지 있는 것만
        try:
            img = requests.get(o["primaryImage"], timeout=30).content
            pil = normalize(io.BytesIO(img))
            ingest(pil, source_type="museum", license="CC0",
                   attribution=o.get("artistDisplayName") or "The Met (CC0)",
                   personas=personas,
                   tags={"query": query, "dept": o.get("department"),
                         "title": o.get("title")},
                   commercial_ok=True)
            n += 1
        except Exception as e:
            print("  skip", oid, repr(e)[:60])
        time.sleep(0.2)  # 레이트리밋 예의
        if n >= limit:
            break
    print(f"  [{query}] seeded {n} (personas={personas})")
    return n


def seed_persona(persona, per_query=5):
    queries, personas = PERSONA_QUERIES[persona]
    return sum(_seed_query(q, personas, per_query) for q in queries)


def seed_all(per_query=5):
    """전 카테고리를 고르게. 각 persona × 검색어당 per_query장."""
    total = sum(seed_persona(p, per_query) for p in PERSONA_QUERIES)
    print("TOTAL museum CC0 seeded:", total)
    return total


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "all":
        seed_all()
    elif arg in PERSONA_QUERIES:
        seed_persona(arg)
    else:                       # 임의 단일 쿼리(레거시 호환)
        _seed_query(arg, ["light", "color", "composition", "mood"], 50)
