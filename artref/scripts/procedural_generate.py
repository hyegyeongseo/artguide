"""procedural_generate.py — 절차적(도식) 레퍼런스 생성기. plan → 이미지 폴더 + manifest.jsonl.

생성 모델 없이 PIL+numpy 로 직접 그린다 → **무료 · 100% 자체소유 · 라벨 정확**. feel 축의 *구조적* 예시
(구도 그리드·명도단계/notan·구/큐브 음영·투시선·지평선·겹침)에 적합하다. imagen_generate.py / gemini_generate.py
와 **동일한 plan·manifest 규약**을 쓰므로 ingest_ai_examples.py 가 그대로 먹는다.

plan 항목에 `"proc": "<렌더러>"` 가 있어야 그 도식으로 그린다(없으면 건너뜀). 렌더러 목록은 RENDERERS 참고.
각 항목의 n 만큼 *변형*(seed=index·j)을 만든다 — 같은 도식이라도 위치·개수·광원 방향이 달라진다.

의존성: pillow, numpy (앱/CLIP 불필요 → 호스트에서도 실행 가능).
실행:
  python scripts/procedural_generate.py gen_plans/coverage_fill_procedural.json --out /tmp/gen_out
  # 그다음(QC+적재 — 영속 상태파일!):
  python scripts/ingest_ai_examples.py /tmp/gen_out --state /tmp/gen_out/_ingest_state.txt \
      --license "Procedural (self-owned)" --attribution "Procedural diagram (QC-gated)"

참고: 도식은 작성-즉시-정답이라, QC 의 CLIP 개념일치에서 가끔 낮게 나올 수 있다. 거부되면 _qc_rejected.jsonl 을
보고 concept 문구를 다듬거나, 신뢰하는 배치이므로 QC 임계값을 낮춰 재적재한다.
"""
import os
import sys
import json
import math
import random
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont

S = 512                       # 캔버스 한 변
BG = (250, 250, 249)          # 배경(크림빛 화이트)
INK = (36, 34, 31)            # 잉크
MID = (140, 140, 138)
LINE = (210, 208, 206)


def _font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    try:
        return ImageFont.load_default(sz)        # Pillow ≥10
    except Exception:
        return ImageFont.load_default()


def _canvas(bg=BG):
    img = Image.new("RGB", (S, S), bg)
    return img, ImageDraw.Draw(img)


def _gray(v):                # 0..1 → RGB 그레이
    g = int(round(np.clip(v, 0, 1) * 255))
    return (g, g, g)


def _thirds(d, faint=LINE):
    for k in (1, 2):
        x = S * k // 3
        d.line([(x, 0), (x, S)], fill=faint, width=2)
        d.line([(0, x), (S, x)], fill=faint, width=2)


def _sphere(r, light=(-0.5, -0.6, 0.65), ambient=0.2, bounce=0.10):
    """Lambert 음영 구. RGBA(원 밖 투명). ambient 낮을수록 고대비(chiaroscuro)."""
    n = 2 * r
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    nx, ny = (xx - r) / r, (yy - r) / r
    rr = nx * nx + ny * ny
    mask = rr <= 1.0
    nz = np.sqrt(np.clip(1 - rr, 0, 1))
    L = np.array(light, float)
    L = L / (np.linalg.norm(L) + 1e-9)
    dot = nx * L[0] + ny * L[1] + nz * L[2]
    val = ambient + (1 - ambient) * np.clip(dot, 0, 1)      # 빛
    val = val + np.clip(-dot, 0, 1) * bounce                # 반사광(그림자측 약하게)
    val = np.clip(val, 0, 1)
    g = (val * 255).astype("uint8")
    rgba = np.dstack([g, g, g, (mask * 255).astype("uint8")])
    return Image.fromarray(rgba, "RGBA"), L


def _cast(d, cx, cy, r, L):
    """접지 그림자 — 구 바로 아래, 광원 반대쪽으로 늘어난 타원. (cx,cy)=구의 바닥."""
    ox, oy = -L[0] * r * 0.7, r * 0.12
    d.ellipse([cx + ox - r * 1.15, cy + oy - r * 0.22,
               cx + ox + r * 1.15, cy + oy + r * 0.22], fill=(214, 212, 210))


def _blob(d, cx, cy, rx, ry, fill):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)


# ───────────────────────── 구도 ─────────────────────────
def rule_of_thirds(rng):
    img, d = _canvas()
    _thirds(d)
    ix, iy = rng.choice([1, 2]), rng.choice([1, 2])
    fx, fy = S * ix // 3, S * iy // 3
    _blob(d, fx, fy, 48, 48, INK)
    d.ellipse([fx - 60, fy - 60, fx + 60, fy + 60], outline=(255, 133, 52), width=3)
    return img


def negative_space(rng):
    img, d = _canvas()
    side = rng.choice([0, 1])
    cx = S * (0.22 if side else 0.78)
    _blob(d, cx, S * rng.uniform(0.45, 0.62), 46, 70, INK)
    return img


def asymmetric_balance(rng):
    img, d = _canvas()
    big = rng.choice([0, 1])
    bx = S * (0.3 if big else 0.7)
    _blob(d, bx, S * 0.55, 80, 80, INK)
    sx = S * (0.72 if big else 0.3)
    for _ in range(rng.randint(2, 3)):
        _blob(d, sx + rng.randint(-40, 40), S * rng.uniform(0.35, 0.72),
              rng.randint(16, 26), rng.randint(16, 26), (90, 88, 86))
    return img


def leading_lines(rng):
    img, d = _canvas()
    fx, fy = S * rng.uniform(0.4, 0.62), S * rng.uniform(0.36, 0.5)
    for sx in (0, S * 0.25, S * 0.75, S):
        d.line([(sx, S), (fx, fy)], fill=MID, width=3)
    _blob(d, fx, fy, 26, 26, INK)
    return img


# ───────────────────────── 명암 ─────────────────────────
def notan(rng):
    img, d = _canvas((255, 255, 255))
    for _ in range(rng.randint(3, 5)):
        x, y = rng.randint(40, S - 160), rng.randint(40, S - 160)
        w, h = rng.randint(90, 200), rng.randint(90, 200)
        if rng.random() < 0.5:
            d.rectangle([x, y, x + w, y + h], fill=(0, 0, 0))
        else:
            d.ellipse([x, y, x + w, y + h], fill=(0, 0, 0))
    return img


def three_value(rng):
    img, d = _canvas((238, 238, 236))       # light
    d.rectangle([0, int(S * rng.uniform(0.45, 0.6)), S, S], fill=_gray(0.45))  # mid 바닥
    _blob(d, S * rng.uniform(0.35, 0.6), S * 0.5, 90, 110, _gray(0.12))        # dark 주제
    return img


def value_scale(rng):
    img, d = _canvas()
    steps = rng.choice([5, 7, 9])
    bw = S // steps
    for i in range(steps):
        v = 1 - i / (steps - 1)
        d.rectangle([i * bw, S * 0.32, (i + 1) * bw, S * 0.68], fill=_gray(v))
    d.text((10, S * 0.7), "white", font=_font(20), fill=INK)
    d.text((S - 70, S * 0.7), "black", font=_font(20), fill=INK)
    return img


def chiaroscuro(rng):
    img, d = _canvas((30, 30, 30))           # 어두운 배경 → 고대비
    r = 150
    sp, L = _sphere(r, light=(rng.uniform(-0.7, -0.3), -0.6, 0.6), ambient=0.06)
    cx, cy = S // 2, S // 2
    _cast(d, cx, cy + r, r, L)
    img.paste(sp, (cx - r, cy - r), sp)
    return img


# ───────────────────────── 빛 ─────────────────────────
def sphere_light(rng):
    img, d = _canvas()
    r = 150
    L_in = (rng.uniform(-0.7, 0.0), -0.6, 0.6)
    sp, L = _sphere(r, light=L_in, ambient=0.2)
    cx, cy = S // 2, int(S * 0.45)
    _cast(d, cx, cy + r, r, L)
    img.paste(sp, (cx - r, cy - r), sp)
    return img


def sphere_labeled(rng):
    img, d = _canvas()
    r = 130
    sp, L = _sphere(r, light=(-0.5, -0.55, 0.65), ambient=0.2)
    cx, cy = int(S * 0.42), int(S * 0.44)
    _cast(d, cx, cy + r, r, L)
    img.paste(sp, (cx - r, cy - r), sp)
    f = _font(16)

    def lab(px, py, tx, ty, text):
        tx = min(tx, S - 116)                      # 우측 잘림 방지
        d.line([(px, py), (tx, ty)], fill=MID, width=2)
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=INK)
        d.text((tx, ty - 8), text, font=f, fill=INK)
    lab(cx - int(r * 0.4), cy - int(r * 0.45), cx + r + 14, cy - r, "highlight")
    lab(cx + int(r * 0.4), cy + int(r * 0.2), cx + r + 14, cy - r // 3, "core shadow")
    lab(cx + int(r * 0.6), cy + int(r * 0.55), cx + r + 14, cy + r // 3, "reflected")
    lab(cx, cy - int(r * 0.05), cx + r + 14, cy + r, "terminator")
    lab(cx + int(r * 1.0), cy + r + 8, cx - r + 10, cy + r + 40, "cast shadow")
    return img


def cube_planes(rng):
    img, d = _canvas()
    cx, cy, s = S // 2, S // 2, 110
    top_left = rng.choice([True, False])
    # 오블리크 큐브: 윗면(밝음)·옆면(중간)·앞면(어두움)
    front = [(cx - s, cy - s // 2), (cx + s, cy - s // 2), (cx + s, cy + s), (cx - s, cy + s)]
    dx = -s * 0.5 if top_left else s * 0.5
    top = [(cx - s, cy - s // 2), (cx + s, cy - s // 2),
           (cx + s + dx, cy - s), (cx - s + dx, cy - s)]
    side = [(cx + s, cy - s // 2), (cx + s + dx, cy - s),
            (cx + s + dx, cy + s - s // 2), (cx + s, cy + s)]
    d.polygon(front, fill=_gray(0.45), outline=INK)
    d.polygon(side, fill=_gray(0.62), outline=INK)
    d.polygon(top, fill=_gray(0.9), outline=INK)
    return img


# ───────────────────────── 원근 ─────────────────────────
def _horizon(d, hy):
    d.line([(0, hy), (S, hy)], fill=MID, width=2)


def one_point(rng):
    img, d = _canvas()
    hy = int(S * rng.uniform(0.45, 0.55))
    vp = (int(S * rng.uniform(0.4, 0.6)), hy)
    _horizon(d, hy)
    for corner in [(0, 0), (S, 0), (0, S), (S, S)]:
        d.line([corner, vp], fill=LINE, width=2)
    # 바닥 격자
    for gx in range(0, S + 1, S // 8):
        d.line([(gx, S), vp], fill=(225, 224, 222), width=1)
    d.ellipse([vp[0] - 4, vp[1] - 4, vp[0] + 4, vp[1] + 4], fill=INK)
    return img


def two_point(rng):
    img, d = _canvas()
    hy = int(S * rng.uniform(0.4, 0.6))
    _horizon(d, hy)
    vL, vR = (-60, hy), (S + 60, hy)
    bx = int(S * rng.uniform(0.42, 0.58))
    top, bot = hy - rng.randint(60, 120), hy + rng.randint(60, 120)
    for vy in (top, bot, (top + bot) // 2):
        d.line([(bx, vy), vL], fill=LINE, width=2)
        d.line([(bx, vy), vR], fill=LINE, width=2)
    d.line([(bx, top), (bx, bot)], fill=INK, width=3)   # 가까운 수직 모서리
    return img


def three_point(rng):
    img, d = _canvas()
    hy = int(S * 0.7)
    _horizon(d, hy)
    vL, vR, vTop = (-80, hy), (S + 80, hy), (S // 2, -160)
    bx, by = S // 2, hy + 10
    for v in (vL, vR, vTop):
        for off in (-50, 0, 50):
            d.line([(bx + off, by), v], fill=LINE, width=2)
    d.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=INK)
    return img


# ───────────────────── 깊이·대기·지평선 ─────────────────────
def atmospheric_value(rng):
    img, d = _canvas((232, 236, 240))
    layers = rng.randint(3, 4)
    base = int(S * 0.55)
    for i in range(layers):
        v = 0.25 + 0.5 * (i / max(1, layers - 1))     # 뒤로 갈수록 밝게
        y = base + i * 26
        pts = [(0, y)]
        for x in range(0, S + 1, 64):
            pts.append((x, y - rng.randint(0, 46) - (layers - i) * 6))
        pts += [(S, y), (S, S), (0, S)]
        d.polygon(pts, fill=_gray(v))
    return img


def overlap_depth(rng):
    img, d = _canvas()
    shapes = [(S * 0.62, S * 0.5, 110, _gray(0.2)),   # 가까움(크고 어두움) — 마지막에 그림
              (S * 0.45, S * 0.45, 90, _gray(0.45)),
              (S * 0.32, S * 0.4, 72, _gray(0.68))]    # 멈(작고 밝음)
    for cx, cy, r, fill in reversed(shapes):           # 먼 것부터 → 가까운 것이 덮음
        _blob(d, cx + rng.randint(-20, 20), cy, r, r, fill)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=INK)
    return img


def horizon_high(rng):
    img, d = _canvas((226, 232, 238))                  # 하늘(작게)
    hy = int(S * rng.uniform(0.22, 0.3))
    _horizon(d, hy)
    d.rectangle([0, hy, S, S], fill=_gray(0.62))        # 넓은 지면
    for _ in range(rng.randint(2, 4)):                  # 지면 위 주제
        x = rng.randint(40, S - 40)
        _blob(d, x, rng.randint(hy + 40, S - 40), 16, 16, INK)
    return img


def horizon_low(rng):
    img, d = _canvas((222, 230, 240))                  # 넓은 하늘
    hy = int(S * rng.uniform(0.72, 0.8))
    d.rectangle([0, hy, S, S], fill=_gray(0.5))         # 작은 지면
    _horizon(d, hy)
    _blob(d, S * rng.uniform(0.3, 0.7), hy, 18, 26, INK)  # 지평선 위 주제
    return img


RENDERERS = {
    "rule_of_thirds": rule_of_thirds, "negative_space": negative_space,
    "asymmetric_balance": asymmetric_balance, "leading_lines": leading_lines,
    "notan": notan, "three_value": three_value, "value_scale": value_scale,
    "chiaroscuro": chiaroscuro, "sphere_light": sphere_light,
    "sphere_labeled": sphere_labeled, "cube_planes": cube_planes,
    "one_point": one_point, "two_point": two_point, "three_point": three_point,
    "atmospheric_value": atmospheric_value, "overlap_depth": overlap_depth,
    "horizon_high": horizon_high, "horizon_low": horizon_low,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="태깅된 절차적 plan(proc 필드 포함)")
    ap.add_argument("--out", default="gen_out")
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding="utf-8-sig"))
    os.makedirs(args.out, exist_ok=True)
    man = open(os.path.join(args.out, "manifest.jsonl"), "a", encoding="utf-8")

    made = skipped = 0
    for i, item in enumerate(plan):
        proc = item.get("proc")
        if not proc or proc not in RENDERERS:
            skipped += 1
            continue
        concept = item["concept"]
        axes = item.get("axes")
        caption = item.get("caption")
        n = int(item.get("n", 1))
        for j in range(n):
            rng = random.Random(1000 * i + j)
            try:
                img = RENDERERS[proc](rng)
            except Exception as e:
                print(f"    렌더 실패 {proc}: {type(e).__name__}: {e}")
                continue
            fn = f"proc_{proc}_{i:03d}_{j:02d}.png"
            img.save(os.path.join(args.out, fn))
            rec = {"file": fn, "concept": concept}
            if axes is not None:
                rec["axes"] = axes
            if caption:
                rec["caption"] = caption
            man.write(json.dumps(rec, ensure_ascii=False) + "\n"); man.flush()
            made += 1
            print(f"  그림  {fn}  ← {proc}")

    print(f"\n생성 {made}장 → {args.out}/  (manifest.jsonl)"
          + (f"  · proc 없는 {skipped}항목 건너뜀" if skipped else ""))
    print(f"다음: python scripts/ingest_ai_examples.py {args.out} "
          f"--state {args.out}/_ingest_state.txt --license \"Procedural (self-owned)\"")


if __name__ == "__main__":
    main()
