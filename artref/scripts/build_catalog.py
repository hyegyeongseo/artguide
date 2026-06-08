"""build_catalog.py — render_poses.py 출력(manifest.jsonl)을 사용자 뷰어용 catalog.json + 썸네일로.

용도: 코치 검색(Qdrant)과 별개로, "한 포즈를 여러 각도로 둘러보는" 사용자 뷰어(pose_viewer.html).
사용:
    pip install pillow
    python build_catalog.py /path/to/output

산출(출력 폴더 안):
  - thumbs/<pose_id>/<view>.webp   (256px 썸네일)
  - catalog.json                   (포즈별 각도 변형 + 태그 + facets)

그다음 폴더 전체를 오브젝트 스토리지+CDN에 올린다:
    aws s3 sync /path/to/output s3://my-bucket/poses --acl public-read
pose_viewer.html은 catalog.json을 읽고 <CDN_BASE>/<path>(원본)·<CDN_BASE>/<thumb>(썸네일)을 띄운다.
"""
import sys, os, json
from collections import defaultdict

try:
    from PIL import Image
except ImportError:
    Image = None

THUMB = 256


def main(out_dir):
    rows = [json.loads(l) for l in open(os.path.join(out_dir, "manifest.jsonl"),
                                        encoding="utf-8") if l.strip()]
    poses = defaultdict(lambda: {"views": []})
    facets = {"category": set(), "body_type": set(), "gender": set(), "region": set()}

    for r in rows:
        p = poses[r["pose_id"]]
        p.update({
            "pose_id": r["pose_id"], "clip": r.get("clip"), "frame": r.get("frame"),
            "category": r.get("category"), "tags": r.get("tags"),
            "body_type": r.get("body_type"), "gender": r.get("gender"),
            "material": r.get("material"),
        })
        for k in facets:
            v = r.get(k)
            if v:
                facets[k].add(v)

        thumb_rel = os.path.join("thumbs", r["pose_id"],
                                 os.path.basename(r["path"]).replace(".png", ".webp"))
        if Image is not None:
            src = os.path.join(out_dir, r["path"])
            dst = os.path.join(out_dir, thumb_rel)
            if os.path.exists(src) and not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                im = Image.open(src).convert("RGBA")
                im.thumbnail((THUMB, THUMB))
                im.save(dst, "WEBP", quality=82, method=6)

        p["views"].append({
            "azimuth": r.get("azimuth"), "elevation": r.get("elevation"),
            "region": r.get("region", "full"),
            "image": r["path"], "thumb": thumb_rel,
        })

    for p in poses.values():
        # full(전신)을 먼저, region별·각도순 정렬 → 뷰어에서 전신→디테일 순으로 보기 좋게
        p["views"].sort(key=lambda v: (v["region"] != "full", v["region"],
                                       v.get("elevation") or 0, v.get("azimuth") or 0))

    catalog = sorted(poses.values(), key=lambda p: p["pose_id"])
    with open(os.path.join(out_dir, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump({"count": len(catalog),
                   "facets": {k: sorted(v) for k, v in facets.items()},
                   "poses": catalog}, f, ensure_ascii=False, indent=2)

    by_cat = defaultdict(int)
    for p in catalog:
        by_cat[p["category"]] += 1
    print(f"{len(catalog)} poses, {len(rows)} images")
    print("by category:", dict(by_cat))
    print("facets:", {k: sorted(v) for k, v in facets.items()})
    if Image is None:
        print("NOTE: Pillow 미설치 — 썸네일 생략. `pip install pillow`")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
