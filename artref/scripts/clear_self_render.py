"""clear_self_render.py — 백본(self_render) 적재분을 비운다(재적재 전 중복 방지).

pipeline.ingest.ingest() 는 매번 새 uuid ref_id 를 만든다. 그래서 그냥 재적재하면 옛 self_render
포인트/행이 그대로 남아 '흰색 옛것 + 차콜 새것'이 중복된다. 이 스크립트로 Qdrant 포인트 + MySQL 행 +
적재 재개 상태파일을 비운 뒤 ingest_manifest 를 다시 돌리면 깨끗하게 교체된다.

S3 객체(images/{ref_id}.png)는 stores/s3.py 에 delete API 가 없어 고아로 남지만 무해하다
(검색/서빙은 Qdrant·MySQL 기준). 정 정리하려면 MinIO 콘솔에서 지운다.

실행(컨테이너, /repo 마운트):
  docker compose exec -w /repo api python scripts/clear_self_render.py          # dry-run(건수만)
  docker compose exec -w /repo api python scripts/clear_self_render.py --yes     # 실제 삭제
"""
import sys
import os

sys.path.insert(0, "api")  # /repo 에서 실행 시 api 패키지 경로
from sqlalchemy import text
from stores.db import engine
from stores import vectors as vstore

STATE = os.path.join("/tmp", "ingest_manifest_state.txt")
SOURCE = "self_render"


def main():
    yes = "--yes" in sys.argv
    with engine.begin() as cx:
        n = cx.execute(text(
            "SELECT COUNT(*) FROM reference_images WHERE source_type=:s"),
            {"s": SOURCE}).scalar()
    print(f"self_render reference_images 행: {n}")
    if not yes:
        print("dry-run — 실제로 지우려면 --yes 를 붙이세요.")
        return

    # 1) Qdrant 포인트 삭제(payload source_type=self_render)
    try:
        vstore.delete_by({"source_type": SOURCE})
        print("Qdrant self_render 포인트 삭제 요청 완료")
    except Exception as e:
        print(f"Qdrant 삭제 경고(계속 진행): {type(e).__name__}: {e}")

    # 2) MySQL 행 삭제
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM reference_images WHERE source_type=:s"), {"s": SOURCE})
    print(f"MySQL self_render 행 {n}개 삭제")

    # 3) 적재 재개 상태파일 제거(안 지우면 재적재가 전부 skip 됨)
    if os.path.exists(STATE):
        os.remove(STATE)
        print(f"상태파일 삭제: {STATE}")
    else:
        print(f"상태파일 없음(건너뜀): {STATE}")

    print("완료 — 이제 scripts/ingest_manifest.py /repo/render_out 로 재적재하세요.")


if __name__ == "__main__":
    main()
