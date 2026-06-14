"""clear_museum.py — museum(CC0) 적재분을 비운다(풍성하게 재시드하기 전 초기화).

seed_museum / seed_museum_aic / seed_feel_axes 로 들어간 source_type="museum" 포인트·행을
Qdrant + MySQL 에서 지운다. clear_self_render.py 와 같은 패턴(SOURCE 만 다름).
museum 시더는 재개 상태파일을 쓰지 않으므로 상태파일 단계는 없다.
self_render / ai_example 은 건드리지 않는다(=백본·생성형 적재분은 그대로 유지).

S3 객체(images/{ref_id}.png)는 stores/s3.py 에 delete API 가 없어 고아로 남지만 무해하다
(검색·서빙은 Qdrant·MySQL 기준). 정 정리하려면 MinIO 콘솔에서 지운다.

실행(컨테이너, /repo 마운트):
  docker compose exec -w /repo api python scripts/clear_museum.py          # dry-run(건수만)
  docker compose exec -w /repo api python scripts/clear_museum.py --yes     # 실제 삭제
"""
import sys

sys.path.insert(0, "api")  # /repo 에서 실행 시 api 패키지 경로
from sqlalchemy import text
from stores.db import engine
from stores import vectors as vstore

SOURCE = "museum"


def main():
    yes = "--yes" in sys.argv
    with engine.begin() as cx:
        n = cx.execute(text(
            "SELECT COUNT(*) FROM reference_images WHERE source_type=:s"),
            {"s": SOURCE}).scalar()
    print(f"{SOURCE} reference_images 행: {n}")
    if not yes:
        print("dry-run — 실제로 지우려면 --yes 를 붙이세요.")
        return

    # 1) Qdrant 포인트 삭제(payload source_type=museum) — 현재 백엔드(클라우드)에 적용
    try:
        vstore.delete_by({"source_type": SOURCE})
        print(f"Qdrant {SOURCE} 포인트 삭제 요청 완료")
    except Exception as e:
        print(f"Qdrant 삭제 경고(계속 진행): {type(e).__name__}: {e}")

    # 2) MySQL 행 삭제
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM reference_images WHERE source_type=:s"), {"s": SOURCE})
    print(f"MySQL {SOURCE} 행 {n}개 삭제")

    print("완료 — 이제 seed_museum / seed_museum_aic / seed_feel_axes 로 풍성하게 재시드하세요.")


if __name__ == "__main__":
    main()
