"""imagen_generate.py — Vertex 이미지 생성 'seam' (Google Gen AI SDK). plan → 폴더 + manifest.jsonl.

★ 스타일은 plan 의 **medium/track 메타데이터**가 STYLE_MAP/TRACK_STYLE 로 구동한다(= 단일 출처).
   concept 는 *의미*만 담는다("still life with three-value massing"). 화풍("oil painting…")은 코드가 붙인다.
   → manifest 의 concept 가 깨끗하게 유지되고, 화풍 추가/교체가 STYLE_MAP 한 줄로 끝난다.
   가드는 medium 별 조건부: 드로잉 medium → '사진·메타프레임 방지', photo medium → photo 가드(나중에 한 줄로 열기).

레거시 Imagen predict API 대신 Gen AI SDK(Vertex 경로, $300 크레딧 적용)를 쓴다. 모델은 IMAGE_MODEL env.
전송 오류(429/quota/transient)엔 지수백오프 재시도. manifest 에 model·생성시각을 남겨 운영 추적.

인증(ADC): gcloud auth application-default login  또는  GOOGLE_APPLICATION_CREDENTIALS=/path/sa.json
환경:  GOOGLE_CLOUD_PROJECT=<ID>  GOOGLE_CLOUD_LOCATION=us-central1  IMAGE_MODEL=imagen-4.0-generate-001
설치:  pip install google-genai pillow
실행:  python scripts/imagen_generate.py gen_plans/coverage_fill_imagen.json --out ./gen_out
"""
import os
import sys
import json
import argparse
import io
import time
from datetime import datetime, timezone

# medium → 화풍 제어문(단일 출처). 새 medium 은 여기 한 줄만 추가.
STYLE_MAP = {
    "watercolor": "watercolor painting, soft color washes, visible paper texture",
    "oil":        "oil painting, painterly visible brush strokes",
    "ink":        "ink wash drawing, brush and ink, tonal values",
    "pencil":     "graphite pencil drawing, hatching, monochrome",
    "digital":    "digital painting, clean stylized rendering",
    "charcoal":     "charcoal drawing, smudged expressive tones, rich darks",
    "pastel":       "soft pastel painting, chalky blended color",
    "gouache":      "gouache painting, flat opaque matte color",
    "woodblock":    "woodblock print, bold flat shapes, limited color, carved lines",
    "impressionist": "impressionist painting, broken color, loose dappled brushwork",
    "expressionist": "expressionist painting, bold gestural brush strokes, vivid color",
    "comic":        "comic and manga ink style, bold linework, flat cel color",
    "sketch":       "loose gestural pencil sketch, quick expressive study lines",
    "conceptart":   "cinematic concept art matte painting, atmospheric digital painting",
    "notan":        "notan study, flat two-value black and white shape design",
    "flatvector":   "flat vector illustration, bold geometric flat color shapes",
    "gameart":      "stylized cel-shaded game art, clean rendering",
    "noir":         "high-contrast noir, dramatic black and white, deep shadows",
    "linocut":      "linocut print, carved bold high-contrast lines",
    # "photo":    "photograph, natural realistic lighting",   # ← 추가 시 _PHOTO_GUARD 적용됨
}
# track 중 '화풍'인 것만(realistic/anime/chibi). landscape/stilllife 는 *소재* → concept 에 이미 있음.
TRACK_STYLE = {
    "anime":     "anime style, cel shading, clean line art",
    "chibi":     "chibi style, cute simplified proportions",
    "realistic": "realistic representational style",
}
# 드로잉 가드: 사진·메타프레임(손/연필/책상/종이) 방지 + 풀프레임.
_DRAW_GUARD = ("full-frame artwork only, the artwork fills the entire frame, "
               "no human hands, no pencils or brushes in frame, no desk, no paper sheet or photo border, "
               "traditional hand-made illustration, not a photograph, no photorealism, no 3d render")
# photo medium 가드(나중에 photo 축 열 때).
_PHOTO_GUARD = "full-frame photograph, natural realistic lighting, no text, no watermark"
# 전역 추가 스타일(선택): 모든 프롬프트 끝에 덧붙임.
_EXTRA = os.environ.get("EXTRA_STYLE", "")

_TRANSIENT = ("429", "quota", "resource exhausted", "resourceexhausted", "rate limit",
              "timeout", "deadline", "unavailable", "503", "500")


def _build_prompt(concept, medium, track):
    parts = [concept]
    if medium in STYLE_MAP:
        parts.append(STYLE_MAP[medium])
    if track in TRACK_STYLE:
        parts.append(TRACK_STYLE[track])
    parts.append(_PHOTO_GUARD if medium == "photo" else _DRAW_GUARD)
    if _EXTRA:
        parts.append(_EXTRA)
    return ", ".join(parts)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _client():
    """Vertex 경로의 Gen AI 클라이언트(크레딧 적용). SDK/자격 없으면 명확히 안내하고 종료."""
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    loc = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not proj:
        print("GOOGLE_CLOUD_PROJECT 미설정 — 프로젝트 '표시이름'이 아니라 'ID' 를 넣으세요.")
        sys.exit(2)
    try:
        from google import genai
    except Exception as e:
        print(f"google-genai SDK 로드 실패: {type(e).__name__}: {e}")
        print("설치: pip install google-genai")
        sys.exit(2)
    try:
        return genai.Client(vertexai=True, project=proj, location=loc)
    except Exception as e:
        print(f"Vertex 클라이언트 생성 실패: {type(e).__name__}: {e}")
        print("ADC 인증(gcloud auth application-default login) + Vertex AI API 활성화를 확인하세요.")
        sys.exit(2)


def _image(client, model, prompt, retries=3):
    """프롬프트 → PIL.Image(1장). 전송 오류(429/quota/transient)엔 지수백오프 재시도.
    안전필터 차단(이미지 0장)·파싱 실패는 재시도해도 같으므로 즉시 None.
    ⚠️ 모델 계열별 호출/응답이 다름(아래 두 분기). SDK 버전이 바뀌면 이 함수만 손보면 된다."""
    from PIL import Image
    from google.genai import types
    for attempt in range(retries):
        try:
            if model.startswith("imagen"):
                resp = client.models.generate_images(
                    model=model, prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1, aspect_ratio="1:1",
                        safety_filter_level="BLOCK_ONLY_HIGH",
                        person_generation="ALLOW_ADULT"))
                imgs = getattr(resp, "generated_images", None) or []
                if not imgs:
                    print("    이미지 0장(안전필터 차단 가능) — 프롬프트 조정.")
                    return None
                return Image.open(io.BytesIO(imgs[0].image.image_bytes)).convert("RGB")
            else:
                resp = client.models.generate_content(model=model, contents=prompt)
                for cand in getattr(resp, "candidates", []) or []:
                    for part in getattr(cand.content, "parts", []) or []:
                        data = getattr(getattr(part, "inline_data", None), "data", None)
                        if data:
                            return Image.open(io.BytesIO(data)).convert("RGB")
                print("    이미지 파트 없음 — 모델/응답 구조 확인.")
                return None
        except Exception as e:
            msg = f"{type(e).__name__}: {e}".lower()
            if attempt < retries - 1 and any(k in msg for k in _TRANSIENT):
                wait = 2 ** attempt
                print(f"    전송 오류 재시도 {attempt + 1}/{retries} ({type(e).__name__}) — {wait}s 대기")
                time.sleep(wait)
                continue
            print(f"    생성 실패: {type(e).__name__}: {e}")
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="계획 JSON(coverage_fill_imagen.json 등)")
    ap.add_argument("--out", default="gen_out")
    ap.add_argument("--model", default=os.environ.get("IMAGE_MODEL", "imagen-4.0-generate-001"),
                    help="Model Garden '이미지 생성' 모델명(또는 IMAGE_MODEL 환경변수)")
    ap.add_argument("--prefix", default="img",
                    help="파일명 접두(배치 구분). 같은 폴더에 여러 배치를 충돌 없이 모을 때 다르게 지정.")
    ap.add_argument("--overwrite", action="store_true",
                    help="이미 있는 파일도 다시 생성(기본은 건너뜀 = 이어받기).")
    ap.add_argument("--start", type=int, default=0,
                    help="이 plan 인덱스부터 생성(이미 뽑은 앞부분 건너뛰기).")
    ap.add_argument("--end", type=int, default=None,
                    help="이 plan 인덱스 직전까지(파이썬 슬라이스). 미지정 시 끝까지.")
    ap.add_argument("--list", action="store_true",
                    help="plan 항목을 인덱스와 함께 출력하고 종료(어디부터 새 항목인지 확인용).")
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding="utf-8-sig"))
    if args.list:
        for i, it in enumerate(plan):
            print(f"{i:03d}: {it.get('medium')}/{it.get('track')}  {it['concept'][:64]}")
        return
    os.makedirs(args.out, exist_ok=True)
    client = _client()
    end = args.end if args.end is not None else len(plan)
    print(f"Vertex 이미지 생성 준비: model={args.model}  범위 [{args.start}:{end}]  (style=STYLE_MAP 구동)")
    man = open(os.path.join(args.out, "manifest.jsonl"), "a", encoding="utf-8")

    made = skipped = skipped_exist = 0
    for i, item in enumerate(plan):
        if i < args.start or i >= end:        # 범위 밖(이미 뽑은 앞부분 등)은 호출 자체 안 함
            continue
        if item.get("gen") == "procedural":
            skipped += 1
            continue
        concept = item["concept"]
        axes = item.get("axes")
        caption = item.get("caption")
        medium = item.get("medium")
        track = item.get("track")
        n = int(item.get("n", 1))
        for j in range(n):
            fn = f"{args.prefix}_{i:03d}_{j:02d}.png"
            fpath = os.path.join(args.out, fn)
            if (not args.overwrite) and os.path.exists(fpath):
                skipped_exist += 1                     # 이어받기: 이미 있는 건 건너뜀(API 호출 안 함)
                continue
            prompt = _build_prompt(concept, medium, track)
            img = _image(client, args.model, prompt)
            if img is None:
                continue
            img.save(fpath)
            rec = {"file": fn, "concept": concept}    # concept=의미만(깨끗)
            if axes is not None:
                rec["axes"] = axes
            if caption:
                rec["caption"] = caption
            if medium:
                rec["medium"] = medium
            if track:
                rec["track"] = track
            rec["model"] = args.model                 # 운영 추적
            rec["generated_at"] = _now()
            man.write(json.dumps(rec, ensure_ascii=False) + "\n"); man.flush()
            made += 1
            print(f"  생성  {fn}  ← {medium}/{track}  {concept[:38]}")

    tail = []
    if skipped_exist:
        tail.append(f"기존 {skipped_exist}장 건너뜀(--overwrite로 강제 재생성)")
    if skipped:
        tail.append(f"절차적 {skipped}항목 건너뜀")
    print(f"\n생성 {made}장 → {args.out}/  (manifest.jsonl 포함)"
          + ("  · " + " · ".join(tail) if tail else ""))
    print(f"다음: python scripts/ingest_ai_examples.py {args.out} "
          f"--state {args.out}/_ingest_state.txt "
          f"--license \"Vertex-Imagen4 (Google IP-indemnified)\"")


if __name__ == "__main__":
    main()
