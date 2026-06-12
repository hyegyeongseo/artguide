"""seed_feel_axes.py — 느낌 축(빛·색·구도·명도)을 Met CC0 로 집중 보강.

audit 결과 느낌 축이 museum 10~20개로 빈약해서, seed_museum 의 단건 시더(_seed_query)를 재사용해
이 축들에 *더 많고 다양한* CC0 레퍼런스를 적재한다. persona 태그는 taxonomy 축과 매칭되게 붙인다.

실행(컨테이너 — 인터넷 + 인프라):
  docker compose exec -w /repo api python scripts/seed_feel_axes.py            # 쿼리당 20장
  docker compose exec -w /repo api python scripts/seed_feel_axes.py 40         # 쿼리당 40장
주의: Met API 레이트리밋. isPublicDomain(CC0)만 적재(상업-클린).
"""
import sys

sys.path.insert(0, "api")
from scripts.seed_museum import _seed_query  # 단건 시더 재사용

# (검색어, personas). personas 는 taxonomy 축의 personas 와 일치시켜 검색 부스트에 걸리게.
FEEL_QUERIES = [
    # light_direction / value_structure (personas: light, technique)
    ("chiaroscuro painting", ["light", "technique"]),
    ("candlelight interior painting", ["light", "mood"]),
    ("rembrandt lighting portrait", ["light", "technique"]),
    ("nocturne night scene painting", ["light", "mood"]),
    ("strong cast shadow still life", ["light", "technique"]),
    # color_harmony (personas: color)
    ("impressionist landscape color", ["color", "mood"]),
    ("still life flowers color", ["color"]),
    ("fauvism vivid color painting", ["color"]),
    ("monochrome tonal painting", ["color", "light"]),
    # composition_balance (personas: composition)
    ("landscape painting composition", ["composition", "mood"]),
    ("still life composition arrangement", ["composition"]),
    ("japanese woodblock composition", ["composition", "mood"]),
]


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    total = 0
    for q, personas in FEEL_QUERIES:
        total += _seed_query(q, personas, per)
    print(f"\nTOTAL feel-axis museum CC0 seeded: {total}")
    print("→ 적재 후 scripts/corpus_audit.py 재실행으로 느낌 축 topScore/공급 확인.")


if __name__ == "__main__":
    main()
