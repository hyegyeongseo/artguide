"""inspect_hands.py — 손 크롭 렌더 품질을 '눈으로' 확인할 콘택트시트 생성.

render_out 안의 손 크롭(예: hand_left_az000.png)을 무작위 표본으로 모아 한 장으로 타일링.
수치(배터리)로는 안 보이는 '손가락 관절·벌어짐 품질'을 사람이 직접 점검하기 위함.

실행: docker compose exec -w /repo api python scripts/inspect_hands.py [render_out_경로] [N]
출력: <render_out>/_hand_contact_sheet.png  → 호스트에서 열어 확인
"""
import sys, os, random
from PIL import Image

REGION_PREFIX = "hand_"  # render_poses 의 크롭 파일명: f"{region}_{side}_az{az:03d}.png"


def collect(root):
    hits = []
    for dp, _, files in os.walk(root):
        for f in files:
            if f.lower().startswith(REGION_PREFIX) and f.lower().endswith(".png"):
                hits.append(os.path.join(dp, f))
    return hits


def flatten(path, size):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGB", im.size, (235, 235, 235))
    bg.paste(im, mask=im.split()[3])
    return bg.resize((size, size))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "/repo/render_out"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 36
    cell, cols = 256, 6
    files = collect(root)
    if not files:
        print(f"손 크롭 없음: {root} ({REGION_PREFIX}*.png)")
        return
    random.shuffle(files)
    files = files[:n]
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (255, 255, 255))
    for i, fp in enumerate(files):
        try:
            sheet.paste(flatten(fp, cell), ((i % cols) * cell, (i // cols) * cell))
        except Exception as e:
            print("  skip", fp, repr(e)[:50])
    out = os.path.join(root, "_hand_contact_sheet.png")
    sheet.save(out)
    print(f"저장: {out}  ({len(files)}장, {cols}x{rows} 타일)")
    print("→ 호스트에서 이 파일을 열어 손가락이 뭉개졌는지/항상 주먹인지 확인하세요.")


if __name__ == "__main__":
    main()
