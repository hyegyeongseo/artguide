"""bria_generate.py — (선택) 생성 단계 'seam'. 계획(plan) → 이미지 폴더 + manifest.jsonl.

Gemini 대신 **Bria** text-to-image 로 AI 예제 후보를 만든다. 토큰/비용 사정으로 생성기를 Bria 로
교체했지만, 다운스트림(QC 게이트·적재)은 전혀 바뀌지 않는다 — 이 스크립트는 ingest_ai_examples.py 가
먹는 폴더 규약(이미지 + manifest.jsonl)을 채워줄 뿐이고, QC 는 *생성기 비종속*이다.
(같은 plan 파일이 gemini_generate.py 와 그대로 호환된다.)

보안: BRIA_API_KEY 는 *백엔드 전용*. 절대 프론트엔드(woz)로 보내지 말 것(Vite VITE_ 접두 금지).

왜 Bria 인가(라이선스): Bria 는 라이선스 정리된 데이터로 학습된 상업용 생성 모델이라, 본 프로젝트의
'commercial_ok' 원칙(상업적으로 쓸 수 있는 자료만)과 결이 맞는다. (적재된 결과는 source_type=ai_example.)

계획 파일(plan.json) 예 — gemini 와 동일:
  [
    {"concept":"single light source on a sphere, clean illustration",
     "axes":["light_direction"], "caption":"광원 하나에서 면이 받는 빛", "n":3},
    {"concept":"limited warm color palette study, flat illustration",
     "axes":["color_harmony"], "n":2}
  ]
  concept 은 영어 권장(CLIP ViT-B-32 영어 학습). caption/axes 는 그대로 manifest 로 흘러간다.

실행:
  export BRIA_API_KEY=...                 # 백엔드 셸/잡 환경에만
  export BRIA_MODEL=2.3                   # (선택) base 모델 버전. 기본 2.3
  python scripts/bria_generate.py gen_plans/feel_axes.json --out gen_out
  # 그다음:  python scripts/ingest_ai_examples.py gen_out   ← 여기서 QC+적재

⚠️ 생성 API 표면은 공급자 버전마다 다르다. Bria 응답/엔드포인트가 바뀌면 _bria_image() 한 곳만
   현재 Bria 문서에 맞게 확인/수정하면 된다(나머지 폴더 규약·manifest 는 그대로).
"""
import os
import sys
import json
import argparse
import io
import time

import requests

# Bria base text-to-image 엔드포인트(모델 버전은 BRIA_MODEL/--model 로). 문서 변경 시 여기만 수정.
_BRIA_BASE = os.environ.get("BRIA_API_BASE", "https://engine.prod.bria-api.com/v1/text-to-image/base")


def _token():
    tok = os.environ.get("BRIA_API_KEY")
    if not tok:
        print("BRIA_API_KEY 가 비어 있습니다(백엔드 환경에만 설정).")
        sys.exit(2)
    return tok


def _bria_image(token, model, prompt):
    """프롬프트 → PIL.Image(첫 결과 1장). 반환 None 이면 이 프롬프트는 건너뜀.

    Bria base 모델은 동기(sync) 호출 시 결과 이미지 URL 을 돌려준다 → 그 URL 을 내려받아 디코드.
    응답 구조가 다른 버전이면(예: result 가 dict, urls 키 명칭 차이) 아래 _extract_url() 만 조정.
    """
    from PIL import Image
    url = f"{_BRIA_BASE}/{model}"
    headers = {"api_token": token, "Content-Type": "application/json"}
    body = {"prompt": prompt, "num_results": 1, "sync": True}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"    생성 실패: {type(e).__name__}: {e}")
        return None
    img_url = _extract_url(data)
    if not img_url:
        print("    이미지 URL 을 못 찾음 — _extract_url() 을 현재 Bria 응답 구조에 맞게 수정하세요.")
        return None
    try:
        ib = requests.get(img_url, timeout=120)
        ib.raise_for_status()
        return Image.open(io.BytesIO(ib.content)).convert("RGB")
    except Exception as e:
        print(f"    이미지 다운로드 실패: {type(e).__name__}: {e}")
        return None


def _extract_url(data):
    """Bria 응답에서 첫 이미지 URL 추출(버전별 변형에 방어적). 구조 바뀌면 여기만 수정."""
    if not isinstance(data, dict):
        return None
    res = data.get("result")
    # 형태 A: {"result": [{"urls": ["..."]}, ...]}
    if isinstance(res, list) and res:
        first = res[0]
        if isinstance(first, dict):
            urls = first.get("urls") or first.get("url")
            if isinstance(urls, list) and urls:
                return urls[0]
            if isinstance(urls, str):
                return urls
        # 형태 B: {"result": ["https://...", ...]}
        if isinstance(first, str):
            return first
    # 형태 C: {"urls": ["..."]} 또는 {"image_url": "..."}
    for k in ("urls", "image_url", "url"):
        v = data.get(k)
        if isinstance(v, list) and v:
            return v[0]
        if isinstance(v, str):
            return v
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="계획 JSON 파일(plan.json)")
    ap.add_argument("--out", default="gen_out", help="출력 폴더")
    ap.add_argument("--model", default=os.environ.get("BRIA_MODEL", "2.3"),
                    help="Bria base 모델 버전(또는 BRIA_MODEL 환경변수). 기본 2.3")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="요청 간 대기(초) — 레이트리밋 회피용")
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding="utf-8-sig"))
    os.makedirs(args.out, exist_ok=True)
    token = _token()
    man = open(os.path.join(args.out, "manifest.jsonl"), "a", encoding="utf-8")

    made = 0
    for i, item in enumerate(plan):
        concept = item["concept"]
        axes = item.get("axes")
        caption = item.get("caption")
        n = int(item.get("n", 1))
        for j in range(n):
            img = _bria_image(token, args.model, concept)
            if img is None:
                continue
            fn = f"gen_{i:03d}_{j:02d}.png"
            img.save(os.path.join(args.out, fn))
            rec = {"file": fn, "concept": concept, "source_model": f"bria:{args.model}"}
            if axes is not None:
                rec["axes"] = axes
            if caption:
                rec["caption"] = caption
            man.write(json.dumps(rec, ensure_ascii=False) + "\n"); man.flush()
            made += 1
            print(f"  생성  {fn}  ← {concept[:48]}")
            if args.sleep:
                time.sleep(args.sleep)

    print(f"\n생성 {made}장 → {args.out}/  (manifest.jsonl 포함, source_model=bria)")
    print(f"다음: python scripts/ingest_ai_examples.py {args.out}   ← QC 게이트 통과분만 적재")


if __name__ == "__main__":
    main()
