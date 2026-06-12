"""run_migrations.py — 마이그레이션을 셸 무관하게 적용.

heredoc(<<'PY') 은 bash 전용이라 PowerShell에선 안 된다. 이 파일을 쓰면 어디서나 동일:
    docker compose exec -w /repo api python scripts/run_migrations.py

MySQL은 ADD COLUMN IF NOT EXISTS 가 없으므로, '이미 적용된' 오류
(1050 table exists / 1060 dup column / 1061 dup key)를 건너뛴다 → 재실행해도 안전.
그 외 오류는 그대로 올려(raise) 진짜 문제를 숨기지 않는다.
"""
import sys
sys.path.insert(0, "api")          # /repo 에서 실행 시 api 패키지 경로
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError
from stores.db import engine

FILES = [
    "api/schema/migrations/002_library_columns.sql",
    "api/schema/migrations/003_practice_log.sql",
    "api/schema/migrations/004_ai_example_source.sql",
]
SKIP_CODES = {1050, 1060, 1061}    # table exists / dup column / dup key


def statements(sql):
    for chunk in sql.split(";"):
        # 주석(-- ) 줄 제거 후 남는 게 있으면 한 문장
        body = "\n".join(l for l in chunk.splitlines()
                         if not l.strip().startswith("--"))
        if body.strip():
            yield body.strip()


def err_code(e):
    orig = getattr(e, "orig", None)
    args = getattr(orig, "args", None)
    return args[0] if args else None


def main():
    for f in FILES:
        print(f"\n[{f}]")
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
    print("\nmigrated ✔")


if __name__ == "__main__":
    main()
