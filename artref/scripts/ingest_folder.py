"""ingest_folder.py — Blender 없이, 임의의 이미지 폴더를 self_render 레퍼런스로 적재.

용도: MakeHuman '포즈 모드'(또는 다른 포징 툴)에서 저장한 몇 장의 포즈 이미지를,
렌더 파이프라인/manifest 없이 곧장 코치 저장소(CLIP→Qdrant + MinIO + DB)에 넣는다.
태그는 CLI로 직접 지정. "일단 몇 장으로 코치 연결을 확인"하는 가장 빠른 경로.

컨테이너에서 실행(ingest가 CLIP/Qdrant/MinIO/DB 접근). 이미지는 /repo 아래(읽기전용)에 둔다:
  docker compose exec -w /repo api python scripts/ingest_folder.py /repo/my_poses \
      --personas pose anatomy --gender female --body-type female_avg \
      --region full --category rest --tags standing relaxed

이미지: png/jpg/webp. 투명 PNG는 회색 배경에 합성. 파일명 기준 재개(상태파일).
주의: 여기 넣는 이미지의 라이선스는 본인 책임. CC0(MakeHuman) 합성 인체 권장, 실제 인물 금지.
"""
import sys, os, json, argparse, tempfile

sys.path.insert(0, "api")  # /repo에서 실행 시 api 패키지 경로 (render_batch와 동일)
from PIL import Image
from pipeline.ingest import ingest

EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def flatten(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (235, 235, 235))
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="적재할 이미지 폴더 (예: /repo/my_poses)")
    ap.add_argument("--personas", nargs="+", default=["pose", "anatomy"],
                    help="앱 페르소나 어휘: pose anatomy hand light color composition 등")
    ap.add_argument("--gender", default=None)
    ap.add_argument("--body-type", dest="body_type", default=None)
    ap.add_argument("--region", default="full", help="full/hand/foot/head")
    ap.add_argument("--category", default=None, help="rest/locomotion/action/expressive 등")
    ap.add_argument("--tags", nargs="*", default=[])
    ap.add_argument("--no-commercial", dest="commercial_ok", action="store_false", default=True)
    ap.add_argument("--attribution", default="manual pose (MakeHuman CC0 base)")
    ap.add_argument("--state", default=os.path.join(tempfile.gettempdir(),
                                                    "ingest_folder_state.jsonl"))
    args = ap.parse_args()

    # 손 부위면 hand 페르소나 자동 보강(코치의 손 검색에 매칭)
    personas = list(args.personas)
    if args.region == "hand" and "hand" not in personas:
        personas.append("hand")
    personas = sorted(set(personas))

    if not os.path.isdir(args.folder):
        print(f"폴더 없음: {args.folder}")
        sys.exit(1)
    files = sorted(f for f in os.listdir(args.folder)
                   if os.path.splitext(f)[1].lower() in EXTS)
    if not files:
        print(f"이미지 없음({sorted(EXTS)}): {args.folder}")
        sys.exit(1)

    done = set()
    if os.path.exists(args.state):
        for l in open(args.state, encoding="utf-8"):
            if l.strip():
                done.add(json.loads(l)["file"])
    sf = open(args.state, "a", encoding="utf-8")

    n = 0
    for fn in files:
        if fn in done:
            continue
        try:
            pil = flatten(os.path.join(args.folder, fn))
            ingest(
                pil,
                source_type="self_render",
                license="CC0",
                personas=personas,
                tags={"category": args.category, "tokens": args.tags,
                      "body_type": args.body_type, "gender": args.gender, "file": fn},
                attribution=args.attribution,
                commercial_ok=args.commercial_ok,
                payload_extra={"body_type": args.body_type, "gender": args.gender,
                               "region": args.region, "category": args.category},
            )
            sf.write(json.dumps({"file": fn}) + "\n")
            sf.flush()
            n += 1
            print("적재:", fn)
        except Exception as e:
            print(f"실패 {fn}: {type(e).__name__}: {e}")
    print(f"완료: {n}장 적재 (스킵 {len(done)}). personas={personas} region={args.region}")
    print(f"상태파일: {args.state}")


if __name__ == "__main__":
    main()
