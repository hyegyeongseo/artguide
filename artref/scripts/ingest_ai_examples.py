"""ingest_ai_examples.py — 생성형 이미지 폴더를 'QC 통과분만' ai_example 로 적재.

ingest_folder.py 와 같은 운영 패턴(argparse·재개 상태파일)인데, 적재 전에 pipeline.ai_qc 게이트를
통과한 것만 넣는다. 생성기(Gemini 등)는 여기서 호출하지 않는다 — 이미 만들어진 폴더를 검사·분류한다.

입력 폴더 규약:
  <folder>/manifest.jsonl   # 이미지 1장당 1줄(권장)
     {"file":"a.png", "concept":"single light source on a sphere",
      "axes":["light_direction"], "caption":"...(선택)"}
  axes 를 비우거나 줄을 생략하면 비전이 자동 태깅한다(파일명만 있는 줄도 허용).
  manifest.jsonl 이 아예 없으면: 폴더의 모든 이미지를 --concept/--axes(공통)로 검사한다.

concept 은 영어 권장(CLIP ViT-B-32 는 영어 학습). 한국어 caption 은 사용자 노출용이라 무관.

실행(컨테이너 — ai_qc 가 CLIP/Qdrant/MinIO/DB 접근):
  docker compose exec -w /repo api python scripts/ingest_ai_examples.py /repo/gen_out
  docker compose exec -w /repo api python scripts/ingest_ai_examples.py /repo/gen_out \
      --concept "limited palette study" --axes color_harmony --strict-anatomy

산출:
  <folder>/_qc_accepted.jsonl  통과·적재(ref_id, supports, scores)
  <folder>/_qc_rejected.jsonl  거부(reasons, scores)  ← 프롬프트/축 교정에 사용
  상태파일(재개)로 이미 처리한 파일은 건너뜀.

주의: 여기 넣는 이미지의 라이선스/저작권은 본인 책임. 생성형 결과물 정책을 확인하세요.
"""
import sys
import os
import json
import argparse
import tempfile

sys.path.insert(0, "api")   # /repo 에서 실행 시 api 패키지 경로(ingest_folder 와 동일)
from PIL import Image
from pipeline.ai_ingest import qc_and_ingest
try:
    from sqlalchemy import text as _sqltext
    from stores.db import engine as _engine
except Exception:
    _engine = None

EXTS = {".png", ".jpg", ".jpeg", ".webp"}

_counters = None


def _seed_counters():
    """기존 ai_…_NNN ref_id 에서 (prefix→max NNN) 수집. *마지막 _NNN 만* 분리 → 축에 밑줄 있어도 안전."""
    c = {}
    if _engine is None:
        return c
    try:
        with _engine.connect() as cx:
            rows = cx.execute(_sqltext(
                # '_'는 LIKE 와일드카드 → 리터럴로 이스케이프. 백슬래시는 드라이버마다 깨져서('\' 문법오류) '!' 사용.
                "SELECT ref_id FROM reference_images WHERE ref_id LIKE 'ai!_%' ESCAPE '!'"
            )).fetchall()
        for row in rows:
            pre, _, nn = str(row[0]).rpartition("_")
            if nn.isdigit():
                c[pre] = max(c.get(pre, 0), int(nn))
    except Exception as e:
        print(f"[ref_id] 카운터 시드 실패(무시, 1부터): {type(e).__name__}: {e}")
    return c


def _next_ref_id(axis, medium, track):
    """조직적 핸들 ai_<축>_<medium>_<track>_NNN. NNN 은 (축,medium,track)별로 기존+이번 연속."""
    global _counters
    if _counters is None:
        _counters = _seed_counters()
    prefix = f"ai_{axis or 'mixed'}_{medium or 'na'}_{track or 'na'}"
    n = _counters.get(prefix, 0) + 1
    _counters[prefix] = n
    return f"{prefix}_{n:03d}"


def flatten(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (235, 235, 235))
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB")


def load_manifest(folder):
    """manifest.jsonl → {file: {concept, axes, caption}}. 없으면 빈 dict(공통 인자 사용)."""
    path = os.path.join(folder, "manifest.jsonl")
    out = {}
    if not os.path.isfile(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if r.get("file"):
                out[r["file"]] = r
        except Exception as e:
            print(f"[manifest] 줄 파싱 실패(무시): {type(e).__name__}: {e}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="생성 이미지 폴더(예: /repo/gen_out)")
    ap.add_argument("--concept", default=None,
                    help="manifest 없는 파일의 공통 concept(영어 권장)")
    ap.add_argument("--axes", nargs="*", default=None,
                    help="manifest 없는 파일의 공통 축(비우면 자동 태깅)")
    ap.add_argument("--license", default="CC0")
    ap.add_argument("--attribution", default="AI-generated example (QC-gated)")
    ap.add_argument("--strict-anatomy", dest="strict", action="store_true", default=False)
    ap.add_argument("--state", default=os.path.join(tempfile.gettempdir(),
                                                    "ingest_ai_examples_state.txt"))
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        print(f"폴더 없음: {args.folder}"); sys.exit(1)
    files = sorted(f for f in os.listdir(args.folder)
                   if os.path.splitext(f)[1].lower() in EXTS)
    if not files:
        print(f"이미지 없음({sorted(EXTS)}): {args.folder}"); sys.exit(1)

    man = load_manifest(args.folder)
    done = set()
    if os.path.exists(args.state):
        done = set(open(args.state, encoding="utf-8").read().split())
    sf = open(args.state, "a", encoding="utf-8")
    acc_f = open(os.path.join(args.folder, "_qc_accepted.jsonl"), "a", encoding="utf-8")
    rej_f = open(os.path.join(args.folder, "_qc_rejected.jsonl"), "a", encoding="utf-8")

    n_acc = n_rej = 0
    for fn in files:
        if fn in done:
            continue
        entry = man.get(fn, {})
        concept = entry.get("concept") or args.concept
        axes = entry.get("axes") if entry.get("axes") is not None else args.axes
        caption = entry.get("caption")
        medium = entry.get("medium")
        track = entry.get("track")
        if not concept:
            print(f"건너뜀(concept 없음 — manifest 또는 --concept 필요): {fn}")
            continue
        axis0 = (axes[0] if axes else None)
        rid = _next_ref_id(axis0, medium, track)
        try:
            pil = flatten(os.path.join(args.folder, fn))
            res = qc_and_ingest(pil, concept, axes, license=args.license,
                                attribution=args.attribution, caption=caption,
                                strict_anatomy=args.strict,
                                medium=medium, track=track, ref_id=rid)
            v = res["verdict"]
            if res["accepted"]:
                n_acc += 1
                rec = {"file": fn, "ref_id": res["ref_id"], "supports": v["supports"],
                       "scores": v["scores"]}
                acc_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); acc_f.flush()
                print(f"  적재  {fn}  → {v['supports']}  ({res['ref_id']})")
            else:
                n_rej += 1
                rec = {"file": fn, "reasons": v["reasons"], "scores": v["scores"]}
                rej_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); rej_f.flush()
                print(f"  거부  {fn}  → {v['reasons'][:1]}")
            sf.write(fn + "\n"); sf.flush()
        except Exception as e:
            print(f"  실패  {fn}: {type(e).__name__}: {e}")

    print(f"\n완료: 적재 {n_acc} · 거부 {n_rej} · 스킵 {len(done)}")
    print(f"  통과: {os.path.join(args.folder, '_qc_accepted.jsonl')}")
    print(f"  거부: {os.path.join(args.folder, '_qc_rejected.jsonl')}  (프롬프트/축 교정에 사용)")
    print(f"  상태파일: {args.state}")


if __name__ == "__main__":
    main()
