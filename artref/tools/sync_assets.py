"""tools/sync_assets.py — 자산 단일 소스(SSOT) 미러링 + CI 가드.

정책: SOURCE=백엔드 artref/assets(저작/생성) → MIRROR=프론트 woz/public(사본).
API 가 /svg 로 서빙하고 테스트가 묶이는 백엔드를 권위로 둔다. 저작이 프론트라면 두 경로를 맞바꾸면 됨.

  python tools/sync_assets.py          # SOURCE → MIRROR 복사
  python tools/sync_assets.py --check  # 다르면 비0 종료(CI)
"""
import os, sys, shutil, filecmp, argparse

SUBDIRS = ("reference", "construction")
COPY_EXT = (".svg", ".json")


def _repo_root():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, "artref")) and os.path.isdir(os.path.join(d, "woz")):
            return d
        d = os.path.dirname(d)
    raise SystemExit("repo 루트(artref/ + woz/)를 찾지 못함")


ROOT = _repo_root()
SOURCE = os.path.join(ROOT, "artref", "assets")
MIRROR = os.path.join(ROOT, "woz", "public")


def _files(base, sub):
    d = os.path.join(base, sub)
    if not os.path.isdir(d):
        return {}
    return {fn: os.path.join(d, fn) for fn in os.listdir(d)
            if fn.lower().endswith(COPY_EXT) and os.path.isfile(os.path.join(d, fn))}


def _plan():
    to_copy, extra = [], []
    for sub in SUBDIRS:
        src, dst = _files(SOURCE, sub), _files(MIRROR, sub)
        for name, sp in src.items():
            dp = dst.get(name)
            if dp is None or not filecmp.cmp(sp, dp, shallow=False):
                to_copy.append((sub, name))
        for name in dst:
            if name not in src:
                extra.append((sub, name))
    return to_copy, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="검사만(다르면 비0 종료) — CI")
    ap.add_argument("--prune", action="store_true", help="소스에 없는 미러 잉여 삭제")
    args = ap.parse_args()
    to_copy, extra = _plan()
    if args.check:
        if to_copy or extra:
            print("자산 드리프트 — `python tools/sync_assets.py` 로 동기화하세요:")
            for sub, n in to_copy:
                print(f"  · 미러 누락/구버전: {sub}/{n}")
            for sub, n in extra:
                print(f"  · 미러 잉여: {sub}/{n}")
            sys.exit(1)
        print("자산 동기 상태 OK (백엔드 == 프론트)")
        return
    for sub, name in to_copy:
        os.makedirs(os.path.join(MIRROR, sub), exist_ok=True)
        shutil.copy2(os.path.join(SOURCE, sub, name), os.path.join(MIRROR, sub, name))
        print(f"  → {sub}/{name}")
    for sub, name in extra:
        if args.prune:
            os.remove(os.path.join(MIRROR, sub, name)); print(f"  ✗ 삭제 {sub}/{name}")
        else:
            print(f"  ! 미러 잉여: {sub}/{name} (지우려면 --prune)")
    print(f"동기화 완료: {len(to_copy)}개 갱신" + (f", 잉여 {len(extra)}개" if extra else ""))


if __name__ == "__main__":
    main()
