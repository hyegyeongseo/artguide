"""ingest_manifest.py — render_poses.py 가 만든 manifest.jsonl 을 코치 저장소에 적재.

render_poses → <OUT_DIR>/manifest.jsonl (이미지 1장당 1줄) → 여기서 ingest()로
CLIP→Qdrant + MinIO + MySQL 적재. region/body_type/gender/category 를 payload_extra로
넘겨 search.py 필터 키와 일치시킨다(손 크롭이 region=hand 로 검색되게).

manifest 한 줄 스키마(render_poses.write_manifest 기준):
  {id, pose_id, clip, frame, azimuth, elevation, category, tags, body_type, gender, region, path}

실행(컨테이너, /repo 마운트에서):
  docker compose exec -w /repo api python scripts/ingest_manifest.py /repo/render_out
  # 인자 = OUT_DIR (manifest.jsonl 과 이미지가 있는 폴더)

재개: 적재한 rid 를 상태파일에 기록 → 다시 돌리면 건너뜀.
주의: 여기 넣는 이미지의 라이선스는 본인 책임. CC0(MakeHuman) 합성 인체 권장, 실제 인물 금지.
"""
import sys
import os
import io
import json

sys.path.insert(0, "api")  # /repo 에서 실행 시 api 패키지 경로
# 무거운 의존(PIL / pipeline.ingest→sqlalchemy·qdrant 등)은 사전 점검 뒤 main 안에서 로드한다.
# → venv 에 백엔드 deps 가 없어도 [점검]은 돌아간다. 실제 적재는 백엔드 컨테이너에서.

STATE = os.path.join("/tmp", "ingest_manifest_state.txt")


def personas_for(region, category):
    """region/category → 앱 persona 어휘(pose/anatomy/hand/...). taxonomy persona와 매칭."""
    if region == "hand":
        return ["hand", "anatomy"]
    if region in ("foot", "head"):
        return ["anatomy", "pose"]
    # 전신
    base = ["pose", "anatomy"]
    if category in ("perspective", "foreshortening"):
        base.append("perspective")
    return sorted(set(base))


def flatten(path):
    from PIL import Image
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        # 투명 배경을 흰색 근처(235)에 합성하면 밝은 3D 피규어가 흰 카드에서 묻힌다.
        # → 중립 차콜에 합성해 형체가 어디서든 보이게(ml/normalize._ALPHA_BG 와 동일 톤). 톤 조절 가능.
        bg = Image.new("RGB", im.size, (58, 61, 67))
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB")


def load_done():
    if os.path.exists(STATE):
        return set(open(STATE, encoding="utf-8").read().split())
    return set()


def _resolve(out_dir, rel):
    """매니페스트 path/rel → 실제 파일 경로. 슬래시 정규화 + 절대경로 폴백(없으면 None)."""
    rel = (rel or "").replace("\\", "/").lstrip("/")
    cand = os.path.normpath(os.path.join(out_dir, *rel.split("/")))
    if os.path.isfile(cand):
        return cand
    if os.path.isabs(rel) and os.path.isfile(rel):
        return rel
    return None


def _precheck(out_dir, lines):
    """전체를 스캔해 디스크 존재 수를 센다 → 경로/실행위치 불일치를 시작부터 드러낸다."""
    present, first_miss = 0, None
    for l in lines:
        try:
            m = json.loads(l)
        except Exception:
            continue
        if _resolve(out_dir, m.get("path") or m.get("rel")):
            present += 1
        elif first_miss is None:
            first_miss = m.get("path") or m.get("rel")
    print(f"[점검] out_dir = {out_dir}")
    print(f"[점검] cwd     = {os.getcwd()}")
    print(f"[점검] 매니페스트 {len(lines)}줄 중 디스크 존재 {present}줄")
    if present == 0:
        print("[경고] 한 장도 디스크에서 못 찾음 — 적재할 이미지가 없습니다. 확인:")
        if first_miss:
            guess = os.path.normpath(os.path.join(out_dir, first_miss.replace("\\", "/")))
            print(f"  · 예상 경로: {guess}")
            print("    → 이 파일이 실제로 있나요? 없으면 렌더가 부분만 됐거나 매니페스트가 옛 계획을 담음")
        print("  · out_dir 인자가 manifest.jsonl 이 든 바로 그 폴더인가요?")
        print("  · render_poses 는 렌더를 스킵/실패해도 매니페스트엔 줄을 남깁니다(append)")
    elif present < len(lines):
        print(f"  (참고: {len(lines) - present}줄은 디스크에 없어 자동 건너뜀 — 존재하는 {present}줄만 적재)")
    return present


def main():
    if len(sys.argv) < 2:
        print("usage: ingest_manifest.py <OUT_DIR>")
        sys.exit(1)
    out_dir = os.path.abspath(sys.argv[1])
    mf = os.path.join(out_dir, "manifest.jsonl")
    if not os.path.isfile(mf):
        print(f"manifest 없음: {mf}")
        sys.exit(1)

    lines = [l for l in open(mf, encoding="utf-8") if l.strip()]
    if _precheck(out_dir, lines) == 0:
        print("\n중단: 디스크에서 찾은 이미지가 없어 적재를 진행하지 않습니다(위 확인사항 참고).")
        sys.exit(2)

    try:
        from pipeline.ingest import ingest
    except ModuleNotFoundError as e:
        print(f"\n[점검은 통과] 하지만 적재 의존이 없습니다: {e.name}")
        print("실제 적재는 백엔드 컨테이너에서 실행하세요(DB·Qdrant·S3 연결 필요):")
        print("  docker compose exec -w /repo api python scripts/ingest_manifest.py /repo/render_out")
        sys.exit(3)

    done = load_done()
    n_ok, n_skip, n_err, n_miss = 0, 0, 0, 0
    with open(mf, encoding="utf-8") as f, open(STATE, "a", encoding="utf-8") as st:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except Exception:
                n_err += 1
                continue
            rid = m.get("id") or m.get("rid") or m.get("pose_id")
            if rid in done:
                n_skip += 1
                continue
            rel = m.get("path") or m.get("rel")
            if not rel:
                print(f"manifest 줄에 path 없음(건너뜀): {rid}")
                n_err += 1
                continue
            img_path = _resolve(out_dir, rel)
            if img_path is None:
                n_err += 1
                if n_miss < 5:
                    print(f"이미지 없음(건너뜀): {os.path.normpath(os.path.join(out_dir, rel.replace(chr(92), '/')))}")
                elif n_miss == 5:
                    print("  ... 이후 '이미지 없음' 로그는 생략(끝에 합계).")
                n_miss += 1
                continue
            region = m.get("region", "full")
            category = m.get("category")
            try:
                pil = flatten(img_path)
                ref_id = ingest(
                    pil,
                    source_type="self_render",
                    license="CC0",
                    personas=personas_for(region, category),
                    tags=m.get("tags", []),
                    attribution="self render (MakeHuman CC0 base)",
                    commercial_ok=True,
                    render_params={k: m.get(k) for k in
                                   ("clip", "frame", "azimuth", "elevation", "pose_id")},
                    payload_extra={"region": region, "category": category,
                                   "body_type": m.get("body_type"),
                                   "gender": m.get("gender")},
                )
                st.write(rid + "\n")
                st.flush()
                n_ok += 1
                if n_ok % 25 == 0:
                    print(f"  ... 적재 {n_ok}장")
            except Exception as e:
                print(f"적재 실패({rid}): {type(e).__name__}: {e}")
                n_err += 1

    print(f"\n완료: 적재 {n_ok} / 건너뜀 {n_skip} / 오류 {n_err}")
    print("커버리지 점검: python scripts/coverage_report.py")


if __name__ == "__main__":
    main()
