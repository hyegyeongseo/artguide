"""resolve_stale_misses.py — 코퍼스 보강으로 더는 miss 가 아닌 옛 miss_log 행을 resolved 처리.

적재 후 miss_log 엔 '적재 전' 잔재가 남는다(예: 손 레퍼런스 1440개 적재했는데도 옛 hand miss 가 떠 있음).
각 미해결 term 을 *지금* 검색해 더는 miss 가 아니면 resolved=1 로 정리한다. --dry 면 표시만.

실행:
  docker compose exec -w /repo api python scripts/resolve_stale_misses.py --dry   # 미리보기
  docker compose exec -w /repo api python scripts/resolve_stale_misses.py          # 실제 정리
"""
import sys

sys.path.insert(0, "api")
from sqlalchemy import text
from stores.db import engine
from pipeline.search import search_text, is_miss
from pipeline import corpus_audit as CA


def main():
    dry = "--dry" in sys.argv

    with engine.begin() as cx:
        rows = [(mid, term, ctx) for mid, term, ctx in cx.execute(text(
            "SELECT id, term, context FROM miss_log WHERE resolved=0"))]
    if not rows:
        print("미해결 miss 없음.")
        return

    stale = CA.resolvable_misses(rows, lambda t: search_text(t, None), is_miss)
    print(f"미해결 {len(rows)}개 중 이제는 검색되는(정리 대상) {len(stale)}개:")
    for mid, term, top in stale:
        print(f"  id={mid}  top={top}  '{term[:56]}'")

    if dry:
        print("\n--dry: 변경 없음. 실제 정리하려면 --dry 빼고 재실행.")
        return
    if not stale:
        return
    ids = [mid for mid, _, _ in stale]
    with engine.begin() as cx:
        from sqlalchemy import bindparam
        cx.execute(text("UPDATE miss_log SET resolved=1 WHERE id IN :ids")
                   .bindparams(bindparam("ids", expanding=True)), {"ids": ids})
    print(f"\n{len(ids)}개 resolved=1 처리 완료.")


if __name__ == "__main__":
    main()
