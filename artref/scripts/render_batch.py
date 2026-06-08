"""render_batch.py — Blender 렌더 출력(manifest.jsonl)을 앱의 검색 저장소로 적재.

올려준 render_poses.py가 만든 <OUT_DIR>/manifest.jsonl + 투명 PNG를 읽어,
포즈당 '대표 각도' 몇 장만 ingest()로 적재한다(CLIP→Qdrant + MinIO + MySQL).
source_type="self_render"로 태깅 → search.py의 SOURCE_PREF가 pose/anatomy/hand
질의에 self_render를 가산 부스트하므로, 코치가 미술관 데생보다 이 렌더를 먼저 띄운다.

컨테이너 안에서 실행(ingest가 CLIP/Qdrant/MinIO/DB에 접근). 렌더 출력은 컨테이너가
읽을 수 있는 곳에 둔다(예: artref/renders → /repo/renders, /repo는 읽기전용 마운트):
    docker compose exec -w /repo api python scripts/render_batch.py /repo/renders

옵션:
    --views 0 90 135   적재할 대표 azimuth(도)만. 8각도 전부는 CLIP상 거의 중복이라 비권장.
                       빈 값(--views)으로 주면 전부 적재.
    --limit N          테스트용 N장만 적재(얇은 슬라이스 검증용).
    --state PATH       중단·재개 상태파일(기본 /tmp). manifest의 image id로 스킵.

처음엔 얇게: 포즈 몇 개만 렌더 → 이걸로 적재 → "동세가 약해요" 질의에 내 렌더가
부스트되어 뜨는지 확인 → 되면 매트릭스(클립×각도×체형) 키워 대량 렌더.
"""
import sys, os, json, argparse, tempfile

sys.path.insert(0, "api")  # /repo에서 실행 시 api 패키지 경로 (seed_museum과 동일)
from PIL import Image
from pipeline.ingest import ingest

# 렌더 category → 앱 persona (taxonomy 어휘: pose/anatomy/hand). SOURCE_PREF가 이들에 부스트.
CATEGORY_PERSONAS = {
    "action": ["pose", "anatomy"], "standing": ["pose", "anatomy"],
    "sitting": ["pose", "anatomy"], "other": ["pose", "anatomy"],
}
HAND_TOKENS = {"hand", "hands", "fist", "grip", "finger", "손"}
DEFAULT_VIEWS = [0, 90, 135]  # 정면 · 측면 · 3/4 뒤 (검색 다양성엔 충분, 중복 최소)


def personas_for(row):
    p = list(CATEGORY_PERSONAS.get(row.get("category", "other"), ["pose", "anatomy"]))
    if row.get("region") == "hand" or (set(row.get("tags") or []) & HAND_TOKENS):
        p.append("hand")
    return sorted(set(p))


def flatten_rgba(path):
    """투명 PNG를 중립 회색 배경에 합성 → CLIP 임베딩·표시 일관성."""
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGB", im.size, (235, 235, 235))
    bg.paste(im, mask=im.split()[3])
    return bg


def _reset_self_render(state_path):
    """기존 self_render를 Qdrant + DB에서 제거(깨끗이 재적재용). MinIO 객체는 남지만 무해."""
    from stores.vectors import qc
    from stores.db import engine
    from config import settings
    from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
    from sqlalchemy import text
    flt = Filter(must=[FieldCondition(key="source_type",
                                      match=MatchValue(value="self_render"))])
    try:
        qc.delete(settings.qdrant_collection, points_selector=FilterSelector(filter=flt))
        print("reset: Qdrant self_render 삭제")
    except Exception as e:
        print(f"reset Qdrant 실패(수동 확인 필요): {type(e).__name__}: {e}")
    try:
        with engine.begin() as cx:
            cx.execute(text("DELETE FROM reference_images WHERE source_type='self_render'"))
        print("reset: DB self_render 삭제")
    except Exception as e:
        print(f"reset DB 실패: {type(e).__name__}: {e}")
    if os.path.exists(state_path):
        os.remove(state_path)
        print("reset: 상태파일 삭제")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default="/repo/renders")
    ap.add_argument("--views", type=int, nargs="*", default=DEFAULT_VIEWS,
                    help="적재할 대표 azimuth. 빈 값이면 전부.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--state", default=os.path.join(tempfile.gettempdir(),
                                                    "render_batch_state.jsonl"))
    ap.add_argument("--reset", action="store_true",
                    help="기존 self_render를 Qdrant+DB에서 비우고 새로 적재")
    args = ap.parse_args()

    if args.reset:
        _reset_self_render(args.state)

    manifest = os.path.join(args.out_dir, "manifest.jsonl")
    if not os.path.exists(manifest):
        print(f"manifest 없음: {manifest}")
        sys.exit(1)
    rows = [json.loads(l) for l in open(manifest, encoding="utf-8") if l.strip()]

    # 중단·재개: 적재 완료한 image id 스킵 (manifest의 'id'는 이미지마다 유일)
    done = set()
    if os.path.exists(args.state):
        for l in open(args.state, encoding="utf-8"):
            if l.strip():
                done.add(json.loads(l)["id"])
    state_f = open(args.state, "a", encoding="utf-8")

    views = set(args.views) if args.views else None
    n_ok = n_skip = n_miss = 0
    for r in rows:
        region = r.get("region", "full")
        # 각도 중복 제거는 전신 렌더에만. 디테일 크롭(손/발/머리)은 별개 콘텐츠라 항상 적재.
        if region == "full" and views is not None and r.get("azimuth") not in views:
            continue
        rid = r.get("id") or f'{r.get("pose_id")}_{r.get("azimuth")}'
        if rid in done:
            n_skip += 1
            continue
        img_path = os.path.join(args.out_dir, r["path"])
        if not os.path.exists(img_path):
            print(f"이미지 없음, 건너뜀: {img_path}")
            n_miss += 1
            continue
        try:
            pil = flatten_rgba(img_path)
            ingest(
                pil,
                source_type="self_render",
                license="CC0",
                personas=personas_for(r),
                tags={"category": r.get("category"), "tokens": r.get("tags"),
                      "body_type": r.get("body_type"), "gender": r.get("gender")},
                attribution="self-render (MakeHuman CC0 base)",
                commercial_ok=True,
                render_params={k: r.get(k) for k in
                               ("pose_id", "clip", "frame", "azimuth", "elevation",
                                "body_type", "gender", "material")},
                payload_extra={"body_type": r.get("body_type"), "gender": r.get("gender"),
                               "region": region, "category": r.get("category")},
            )
            state_f.write(json.dumps({"id": rid}) + "\n")
            state_f.flush()
            n_ok += 1
            if n_ok % 10 == 0:
                print(f"... 적재 {n_ok}")
            if args.limit and n_ok >= args.limit:
                print(f"--limit {args.limit} 도달, 중단")
                break
        except Exception as e:
            print(f"적재 실패({rid}): {type(e).__name__}: {e}")
    state_f.close()
    print(f"완료: 적재 {n_ok}, 스킵(기존) {n_skip}, 이미지없음 {n_miss}. "
          f"상태파일: {args.state}")


if __name__ == "__main__":
    main()
