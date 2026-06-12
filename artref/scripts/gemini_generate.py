"""gemini_generate.py — [레거시] 생성 단계 'seam'. 계획(plan) → 이미지 폴더 + manifest.jsonl.

⚠️ 현재 기본 생성기는 scripts/bria_generate.py 입니다(토큰/비용 사정으로 Bria 로 전환). 이 파일은
   참고/폴백용으로 남겨둡니다. 동일한 plan 파일·manifest 규약을 공유하므로 둘은 호환됩니다.

QC 게이트는 *생성기 비종속(generator-agnostic)* 이다 — 이 스크립트는 단지 ingest_ai_examples.py 가
먹을 폴더 규약(이미지 + manifest.jsonl)을 Gemini 로 채워주는 편의 도구일 뿐이다. 다른 생성기를
쓰면 같은 폴더 규약만 맞추면 된다.

보안: GEMINI_API_KEY 는 *백엔드 전용*. 절대 프론트엔드(woz)로 보내지 말 것(Vite VITE_ 접두 금지).
모델: GEMINI_IMAGE_MODEL 환경변수로 지정한다. 이미지 생성 모델/SDK 호출부는 버전에 따라 다르므로
      아래 _gemini_image() 한 곳만 현재 사용하는 모델·SDK 에 맞게 확인/수정하면 된다(나머지는 그대로).

계획 파일(plan.json) 예:
  [
    {"concept":"single light source on a sphere, clean illustration",
     "axes":["light_direction"], "caption":"광원 하나에서 면이 받는 빛", "n":3},
    {"concept":"limited warm color palette study, flat illustration",
     "axes":["color_harmony"], "n":2}
  ]
  concept 은 영어 권장(CLIP ViT-B-32 영어 학습). caption/axes 는 그대로 manifest 로 흘러간다.

실행:
  export GEMINI_API_KEY=...            # 백엔드 셸/잡 환경에만
  export GEMINI_IMAGE_MODEL=<your-image-model>
  python scripts/gemini_generate.py plan.json --out gen_out
  # 그다음:  python scripts/ingest_ai_examples.py gen_out   ← 여기서 QC+적재
"""
import os
import sys
import json
import argparse
import io


def _client():
    """google-genai 클라이언트. SDK/키 없으면 명확히 안내하고 종료."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY 가 비어 있습니다(백엔드 환경에만 설정).")
        sys.exit(2)
    try:
        from google import genai            # pip install google-genai
        return genai.Client(api_key=key)
    except Exception as e:
        print(f"google-genai SDK 로드 실패: {type(e).__name__}: {e}")
        print("설치: pip install google-genai   (또는 사용하는 생성기로 _gemini_image 교체)")
        sys.exit(2)


def _gemini_image(client, model, prompt):
    """프롬프트 → PIL.Image(첫 결과 1장). 반환 None 이면 이 프롬프트는 건너뜀.

    ⚠️ 이미지 생성 API 표면은 모델/SDK 버전마다 다릅니다. *현재 사용하는 모델 문서*로 이 함수를
       확인/수정하세요. 아래는 google-genai 의 일반적 형태에 대한 방어적 구현이며, 응답에서
       바이트(inline_data)를 찾으면 PIL 로 디코드합니다. 응답 구조가 다르면 여기만 고치면 됩니다.
    """
    from PIL import Image
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
    except Exception as e:
        print(f"    생성 실패: {type(e).__name__}: {e}")
        return None
    # 응답에서 첫 이미지 바이트 추출(구조가 다르면 이 부분만 조정)
    try:
        for cand in getattr(resp, "candidates", []) or []:
            for part in getattr(cand.content, "parts", []) or []:
                data = getattr(getattr(part, "inline_data", None), "data", None)
                if data:
                    return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        print(f"    응답 파싱 실패: {type(e).__name__}: {e}")
    print("    이미지 파트를 못 찾음 — _gemini_image() 를 현재 모델 응답 구조에 맞게 수정하세요.")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="계획 JSON 파일(plan.json)")
    ap.add_argument("--out", default="gen_out", help="출력 폴더")
    ap.add_argument("--model", default=os.environ.get("GEMINI_IMAGE_MODEL", ""),
                    help="이미지 모델(또는 GEMINI_IMAGE_MODEL 환경변수)")
    args = ap.parse_args()
    if not args.model:
        print("이미지 모델 미지정 — --model 또는 GEMINI_IMAGE_MODEL 설정 필요.")
        sys.exit(2)

    plan = json.load(open(args.plan, encoding="utf-8-sig"))
    os.makedirs(args.out, exist_ok=True)
    client = _client()
    man = open(os.path.join(args.out, "manifest.jsonl"), "a", encoding="utf-8")

    made = 0
    for i, item in enumerate(plan):
        concept = item["concept"]
        axes = item.get("axes")
        caption = item.get("caption")
        n = int(item.get("n", 1))
        for j in range(n):
            img = _gemini_image(client, args.model, concept)
            if img is None:
                continue
            fn = f"gen_{i:03d}_{j:02d}.png"
            img.save(os.path.join(args.out, fn))
            rec = {"file": fn, "concept": concept}
            if axes is not None:
                rec["axes"] = axes
            if caption:
                rec["caption"] = caption
            man.write(json.dumps(rec, ensure_ascii=False) + "\n"); man.flush()
            made += 1
            print(f"  생성  {fn}  ← {concept[:48]}")

    print(f"\n생성 {made}장 → {args.out}/  (manifest.jsonl 포함)")
    print(f"다음: python scripts/ingest_ai_examples.py {args.out}   ← QC 게이트 통과분만 적재")


if __name__ == "__main__":
    main()
