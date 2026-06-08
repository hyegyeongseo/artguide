"""DB 스키마 적용 (OS 무관). 셸 리다이렉션(`cat | mysql`, `<`) 없이 ddl.sql을 실행.

컨테이너 안에서:
    docker compose exec -w /repo api python scripts/init_db.py
(DB_DSN 환경변수는 compose env_file로 이미 주입됨. mysql 호스트는 네트워크 내부에서 해석.)
"""
import os
import sys
from sqlalchemy import create_engine, text

HERE = os.path.dirname(os.path.abspath(__file__))
DDL_PATH = os.path.join(HERE, "..", "api", "schema", "ddl.sql")


def main():
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN 환경변수가 없습니다. (.env / compose env_file 확인)")
        sys.exit(1)

    with open(DDL_PATH, encoding="utf-8") as f:
        sql = f.read()

    # 세미콜론 기준으로 문장 분리(이 ddl엔 문장 내부 세미콜론이 없음).
    stmts = [s.strip() for s in sql.split(";") if s.strip()]

    engine = create_engine(dsn, pool_pre_ping=True)
    applied = 0
    with engine.begin() as cx:
        for s in stmts:
            cx.execute(text(s))
            applied += 1
    print(f"applied {applied} statements from {os.path.relpath(DDL_PATH)}")

    # 마이그레이션: 기존 adoption_log에 sub_problem 없으면 추가(ADD COLUMN IF NOT EXISTS 미지원 우회)
    with engine.begin() as cx:
        has = cx.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name='adoption_log' "
            "AND column_name='sub_problem'")).scalar()
        if not has:
            cx.execute(text("ALTER TABLE adoption_log ADD COLUMN sub_problem VARCHAR(48)"))
            print("migration: adoption_log.sub_problem 추가")
        else:
            print("migration: adoption_log.sub_problem 이미 존재")


if __name__ == "__main__":
    main()
