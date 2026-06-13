"""run_migrations.py — api/schema/migrations/*.sql 를 번호순으로 *전부* 적용(셸 무관).

heredoc(<<'PY')은 bash 전용이라 PowerShell에선 안 된다. 이 파일을 쓰면 어디서나 동일:
    docker compose exec -w /repo api python scripts/run_migrations.py

동작:
  • migrations/ 디렉터리를 스캔해 파일명(번호 프리픽스) 오름차순으로 전부 적용한다.
    → 새 마이그레이션을 추가할 때 이 파일을 수정할 필요가 없다(NNN_*.sql 을 떨구기만 하면 잡힌다).
      (예전엔 FILES 목록이 004 에서 멈춰 005·006·007 이 조용히 누락됐었다.)
  • MySQL은 ADD COLUMN IF NOT EXISTS 가 없으므로, '이미 적용된' 오류
    (1050 table exists / 1060 dup column / 1061 dup key)는 건너뛴다 → 재실행해도 안전(idempotent).
    그 외 오류는 그대로 올려(raise) 진짜 문제를 숨기지 않는다.

전제: fresh 스키마는 init_db.py(ddl.sql)로 만들고, 이 스크립트는 그 위에 증분 변경을 적용한다.
파일명 번호가 곧 적용 순서이므로 같은 번호를 두 개 쓰지 말 것(정렬이 모호해짐).
"""
import os
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
# /repo 가 아닌 곳에서 실행해도 stores.db 를 임포트할 수 있게 절대경로로 api 패키지 경로 주입.
sys.path.insert(0, os.path.join(HERE, "..", "api"))
MIG_DIR = os.path.join(HERE, "..", "api", "schema", "migrations")

SKIP_CODES = {1050, 1060, 1061}    # table exists / dup column / dup key


def migration_files():
    """migrations/*.sql 를 파일명(번호 프리픽스) 오름차순으로. 번호가 곧 적용 순서."""
    return sorted(glob.glob(os.path.join(MIG_DIR, "*.sql")))


def statements(sql):
    """SQL 본문을 ';' 기준으로 문장 단위 분리. '-- ' 주석 줄은 제거(이 migrations 엔 문장 내부 ';' 없음)."""
    for chunk in sql.split(";"):
        body = "\n".join(l for l in chunk.splitlines()
                         if not l.strip().startswith("--"))
        if body.strip():
            yield body.strip()


def err_code(e):
    orig = getattr(e, "orig", None)
    args = getattr(orig, "args", None)
    return args[0] if args else None


def main():
    # 무거운 임포트(엔진=DB 연결)는 여기서 — 순수 함수(migration_files/statements)는 DB 없이 테스트 가능.
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError
    from stores.db import engine

    files = migration_files()
    if not files:
        print(f"마이그레이션 파일이 없습니다: {MIG_DIR}")
        return
    repo_root = os.path.join(HERE, "..")
    for f in files:
        print(f"\n[{os.path.relpath(f, repo_root)}]")
        sql = open(f, encoding="utf-8").read()
        for s in statements(sql):
            head = s.splitlines()[0][:70]
            try:
                with engine.begin() as cx:
                    cx.execute(text(s))
                print("  ok  :", head)
            except (OperationalError, ProgrammingError, IntegrityError) as e:
                code = err_code(e)
                if code in SKIP_CODES:
                    print("  skip:", head, f"(이미 적용, code {code})")
                else:
                    print("  ERR :", head, f"→ code {code}: {e}")
                    raise
    print(f"\nmigrated ✔  ({len(files)}개 파일)")


if __name__ == "__main__":
    main()
