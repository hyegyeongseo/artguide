"""run_tests.py — tests/ 의 커스텀 러너(파일별 run())를 한 번에 실행.

이 저장소의 테스트는 pytest 가 아니라 파일별 t_*() + run() 규약이고, *파일마다 별도 프로세스*로
도는 것을 전제로 설계됐다(모듈 간 상태/캐시 누수 없이 독립 실행). 그래서 이 러너도 각 테스트
모듈을 `python -m tests.<name>` 서브프로세스로 돌리고, 하나라도 실패하면 비0 종료한다.

CI(.github/workflows/tests.yml)와 로컬에서 한 명령으로 전부:
  artref/api 에서   python run_tests.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(HERE, "tests")


def _modules():
    for fn in sorted(os.listdir(TESTS_DIR)):
        if fn.startswith("test_") and fn.endswith(".py"):
            yield "tests." + fn[:-3]


def main():
    failed = []
    for mod in _modules():
        print(f"\n=== {mod} ===")
        r = subprocess.run([sys.executable, "-m", mod], cwd=HERE)
        if r.returncode != 0:
            failed.append(mod)
            print(f"FAIL  {mod}")
    print("\n" + "=" * 48)
    if failed:
        print(f"실패한 모듈 {len(failed)}개: {', '.join(failed)}")
        sys.exit(1)
    print("모든 테스트 모듈 통과 ✅")


if __name__ == "__main__":
    main()
