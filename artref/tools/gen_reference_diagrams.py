"""gen_reference_diagrams.py — '구축 다이어그램' 라이브러리 확장 세트.

`gen_construction_diagrams.py`(taxonomy 10축 1:1 도식)와 *완전히 같은 스타일 계약*을 따른다:
viewBox 480x480, 동일 색 토큰, <g id="construction"/guide/label> 3레이어 토글, 한글 캡션.

이 파일은 taxonomy 축을 1:1로 덮는 대신, 그 축들을 받쳐 주는 **기초 개념 레퍼런스**를 추가한다
(머리·얼굴·몸통 매스·제스처 문법·마네킹·투시·빛 용어·모서리·색상환·노탄). GUIDE_ASSET.md가 말한
"sub_problem마다 자료를 더 인덱싱할수록 명중률이 오른다"의 svg(도식) 후보를 늘리는 용도다.
각 도식이 어느 축/페르소나를 받치는지는 manifest.json 참고(run_guide(..., asset_index=...)에 그대로 사용).

사실적 인체가 아니라 '어떻게 생각하라'를 보여주는 단순 기하 → 구성상 정확(correct-by-construction).

실행:  python tools/gen_reference_diagrams.py [out_dir]
출력:  <out_dir>/<name>.svg  (+ <out_dir>/manifest.json)  기본 out_dir = ./reference
"""
import colorsys
import json
import math
import os
import sys

W = H = 480
GUIDE = "#c7ccd4"   # 연한 가이드(형태)
CONS = "#e0533d"    # 구축선(빨강-주황)
ACC = "#2f6df0"     # 강조(파랑) — 드물게
INK = "#3a3f47"     # 라벨 텍스트
DASH = "6 5"


def _svg(title, body_guide, body_cons, labels, caption, defs=""):
    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">
  <style>
    .guide {{ fill:none; stroke:{GUIDE}; stroke-width:2.5; }}
    .gfill {{ fill:{GUIDE}; opacity:.18; stroke:none; }}
    .cons  {{ fill:none; stroke:{CONS}; stroke-width:2.5; stroke-linecap:round; stroke-linejoin:round; }}
    .consd {{ fill:none; stroke:{CONS}; stroke-width:2; stroke-dasharray:{DASH}; }}
    .acc   {{ fill:none; stroke:{ACC};  stroke-width:2.5; stroke-linecap:round; }}
    .accd  {{ fill:none; stroke:{ACC};  stroke-width:2; stroke-dasharray:{DASH}; }}
    .dot   {{ fill:{CONS}; stroke:none; }}
    .adot  {{ fill:{ACC}; stroke:none; }}
    .lbl   {{ fill:{INK}; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif; font-size:14px; }}
    .cap   {{ fill:{INK}; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif; font-size:13px; opacity:.8; }}
    .tag   {{ fill:{CONS}; font-family:sans-serif; font-size:12px; font-weight:600; }}
  </style>
  {defs}<g id="guide">{body_guide}</g>
  <g id="construction">{body_cons}</g>
  <g id="label">{labels}
    <text class="cap" x="20" y="{H-18}">{caption}</text>
  </g>
</svg>
"""


def _arrow(x1, y1, x2, y2, cls="acc"):
    """선 + 끝 화살촉."""
    ang = math.atan2(y2 - y1, x2 - x1)
    a = ang + math.radians(150)
    b = ang - math.radians(150)
    L = 14
    hx1, hy1 = x2 + L * math.cos(a), y2 + L * math.sin(a)
    hx2, hy2 = x2 + L * math.cos(b), y2 + L * math.sin(b)
    return (f'<path class="{cls}" d="M{x1:.0f} {y1:.0f} L{x2:.0f} {y2:.0f}"/>'
            f'<path class="{cls}" d="M{x2:.0f} {y2:.0f} L{hx1:.0f} {hy1:.0f} '
            f'M{x2:.0f} {y2:.0f} L{hx2:.0f} {hy2:.0f}"/>')


# ── 1. 머리 구축 (Loomis 정면) ─────────────────────────────────────────────
def head_construction():
    cx = 240
    top, hair, brow, nose, chin = 60, 150, 240, 330, 420  # 등분 기준선
    ball_cy = (top + brow) / 2          # 머리통(공) 중심
    ball_r = (brow - top) / 2
    guide = (f'<circle class="gfill" cx="{cx}" cy="{ball_cy:.0f}" r="{ball_r:.0f}"/>'
             f'<path class="gfill" d="M{cx-ball_r:.0f} {brow} '
             f'C{cx-ball_r:.0f} {chin-20} {cx-50} {chin} {cx} {chin} '
             f'C{cx+50} {chin} {cx+ball_r:.0f} {chin-20} {cx+ball_r:.0f} {brow} Z"/>')
    cons = (
        f'<circle class="cons" cx="{cx}" cy="{ball_cy:.0f}" r="{ball_r:.0f}"/>'   # 머리통 공
        # 양옆 측면 평면(temple plane)
        f'<ellipse class="consd" cx="{cx-ball_r+18:.0f}" cy="{ball_cy:.0f}" rx="20" ry="{ball_r-6:.0f}"/>'
        f'<ellipse class="consd" cx="{cx+ball_r-18:.0f}" cy="{ball_cy:.0f}" rx="20" ry="{ball_r-6:.0f}"/>'
        # 턱
        f'<path class="cons" d="M{cx-ball_r:.0f} {brow} C{cx-ball_r:.0f} {chin-20} {cx-50} {chin} {cx} {chin} '
        f'C{cx+50} {chin} {cx+ball_r:.0f} {chin-20} {cx+ball_r:.0f} {brow}"/>'
        # 세로 중심선
        f'<line class="acc" x1="{cx}" y1="{top}" x2="{cx}" y2="{chin}"/>'
        # 가로 등분선
        f'<line class="consd" x1="{cx-ball_r-20:.0f}" y1="{hair}" x2="{cx+ball_r+20:.0f}" y2="{hair}"/>'
        f'<line class="consd" x1="{cx-ball_r-20:.0f}" y1="{brow}" x2="{cx+ball_r+20:.0f}" y2="{brow}"/>'
        f'<line class="consd" x1="{cx-ball_r-20:.0f}" y1="{nose}" x2="{cx+ball_r+20:.0f}" y2="{nose}"/>'
    )
    labels = (f'<text class="lbl" x="{cx+ball_r+26:.0f}" y="{ball_cy:.0f}">머리통(공)</text>'
              f'<text class="lbl" x="{cx-ball_r-2:.0f}" y="{ball_cy-30:.0f}" text-anchor="end">측면 평면</text>'
              f'<text class="lbl" x="{cx+ball_r+26:.0f}" y="{hair+4}">머리선</text>'
              f'<text class="lbl" x="{cx+ball_r+26:.0f}" y="{brow+4}">눈썹선</text>'
              f'<text class="lbl" x="{cx+ball_r+26:.0f}" y="{nose+4}">코밑</text>'
              f'<text class="lbl" x="{cx+ball_r+26:.0f}" y="{chin+4}">턱끝</text>'
              f'<text class="lbl" x="{cx-6}" y="{top-6}" fill="{ACC}" text-anchor="end">중심선</text>')
    return _svg("head_construction", guide, cons, labels,
                "머리 = 공(머리통) + 턱. 중심선·눈썹선부터 잡고 얼굴은 3등분.")


# ── 2. 얼굴 비율 (정면) ────────────────────────────────────────────────────
def facial_proportion():
    cx, top, chin = 240, 70, 420
    eye_y = (top + chin) / 2            # 눈은 머리 높이의 정중앙
    brow_y, nose_y, mouth_y = 210, 320, 372
    fw = 240                            # 눈높이 얼굴 폭
    left = cx - fw / 2
    fifth = fw / 5
    guide = f'<ellipse class="gfill" cx="{cx}" cy="{(top+chin)/2:.0f}" rx="{fw/2:.0f}" ry="{(chin-top)/2:.0f}"/>'
    # 가로 기준선
    rows = [(top, "머리끝"), (brow_y, "눈썹"), (eye_y, "눈"), (nose_y, "코밑"), (mouth_y, "입"), (chin, "턱")]
    cons = "".join(
        f'<line class="consd" x1="{left:.0f}" y1="{y}" x2="{left+fw:.0f}" y2="{y}"/>'
        for y, _ in rows)
    # 세로 5등분(눈높이)
    cons += "".join(
        f'<line class="consd" x1="{left+fifth*i:.0f}" y1="{eye_y-30:.0f}" x2="{left+fifth*i:.0f}" y2="{eye_y+30:.0f}"/>'
        for i in range(6))
    # 눈 두 개(2번째·4번째 칸)
    for i in (1, 3):
        ex = left + fifth * i + fifth / 2
        cons += f'<ellipse class="cons" cx="{ex:.0f}" cy="{eye_y:.0f}" rx="{fifth/2-4:.0f}" ry="9"/>'
        cons += f'<circle class="dot" cx="{ex:.0f}" cy="{eye_y:.0f}" r="3.5"/>'
    cons += f'<line class="acc" x1="{cx}" y1="{top}" x2="{cx}" y2="{chin}"/>'
    labels = "".join(f'<text class="lbl" x="{left+fw+12:.0f}" y="{y+4}">{name}</text>' for y, name in rows)
    labels += (f'<text class="lbl" x="{cx}" y="{eye_y-38:.0f}" text-anchor="middle">얼굴 너비 = 눈 5칸</text>')
    return _svg("facial_proportion", guide, cons, labels,
                "눈은 머리 높이의 한가운데, 눈과 눈 사이는 눈 하나 폭.")


# ── 3. 몸통 매스 (흉곽·골반 상자) ──────────────────────────────────────────
def torso_box():
    # 흉곽(상자)과 골반(상자)이 척추로 이어지고 서로 반대로 비틀림.
    rib = "M180 100 L300 86 L312 196 L196 214 Z"        # 살짝 기운 흉곽
    pel = "M196 280 L300 292 L292 372 L188 360 Z"       # 반대로 기운 골반
    guide = (f'<path class="gfill" d="{rib}"/><path class="gfill" d="{pel}"/>')
    cons = (
        f'<path class="cons" d="{rib}"/>'
        f'<path class="cons" d="{pel}"/>'
        # 척추 S선
        '<path class="acc" d="M250 150 C262 210 232 250 244 326"/>'
        # 각 매스 기울기선
        '<line class="consd" x1="172" y1="93" x2="312" y2="76"/>'
        '<line class="consd" x1="188" y1="372" x2="304" y2="384"/>'
        # 명치/배꼽 표시
        '<circle class="dot" cx="250" cy="150" r="4"/>'
        '<circle class="dot" cx="244" cy="326" r="4"/>'
    )
    labels = ('<text class="lbl" x="316" y="150">흉곽 상자</text>'
              '<text class="lbl" x="312" y="336">골반 상자</text>'
              '<text class="lbl" x="258" y="246" fill="' + ACC + '">척추</text>'
              '<text class="lbl" x="120" y="86">기울기 ↘</text>'
              '<text class="lbl" x="120" y="388">기울기 ↗</text>')
    return _svg("torso_box", guide, cons, labels,
                "몸통 = 흉곽 상자 + 골반 상자. 둘은 척추로 잇고 서로 반대로 비튼다.")


# ── 4. 제스처 문법 (C·S·I) ─────────────────────────────────────────────────
def gesture_rhythm():
    # 왼쪽: C/S/I 샘플. 오른쪽: 직선 대 곡선으로 받치는 인물.
    guide = ('<circle class="gfill" cx="330" cy="120" r="26"/>'
             '<ellipse class="gfill" cx="318" cy="240" rx="42" ry="64"/>')
    cons = (
        # 샘플
        '<path class="cons" d="M70 90 C40 150 40 200 70 260"/>'       # C
        '<path class="cons" d="M150 90 C120 140 180 200 150 260"/>'   # S
        '<path class="cons" d="M110 300 L110 410"/>'                  # I
        # 인물: 머리→지지발 관통선
        '<path class="acc" d="M330 96 C300 170 360 250 318 410"/>'
        '<circle class="dot" cx="330" cy="96" r="4"/>'
        '<circle class="dot" cx="318" cy="410" r="4"/>'
        # 직선 대 곡선(한쪽 곡선/반대쪽 직선)
        '<path class="cons" d="M300 200 C282 250 286 300 300 350"/>'  # 곡선쪽
        '<line class="consd" x1="350" y1="196" x2="356" y2="356"/>'   # 직선쪽
    )
    labels = ('<text class="lbl" x="58" y="80">C</text>'
              '<text class="lbl" x="138" y="80">S</text>'
              '<text class="lbl" x="98" y="290">I</text>'
              '<text class="lbl" x="250" y="250" fill="' + CONS + '">곡선</text>'
              '<text class="lbl" x="362" y="280">직선</text>'
              '<text class="lbl" x="252" y="130" fill="' + ACC + '">관통선</text>')
    return _svg("gesture_rhythm", guide, cons, labels,
                "모든 선은 C·S·I 중 하나. 한쪽이 곡선이면 반대쪽은 직선으로 받친다.")


# ── 5. 마네킹 블로킹 ───────────────────────────────────────────────────────
def mannequin_blocking():
    guide = ''
    cons = (
        # 머리(달걀)
        '<ellipse class="cons" cx="240" cy="80" rx="26" ry="32"/>'
        # 목
        '<line class="cons" x1="240" y1="112" x2="240" y2="138"/>'
        # 흉곽 상자
        '<path class="cons" d="M204 138 L276 138 L286 222 L194 222 Z"/>'
        # 골반 상자
        '<path class="cons" d="M206 250 L274 250 L282 312 L198 312 Z"/>'
        # 허리 연결
        '<line class="consd" x1="240" y1="222" x2="240" y2="250"/>'
        # 팔(원통)
        '<path class="cons" d="M204 150 q-44 30 -54 86"/>'
        '<path class="cons" d="M276 150 q44 30 54 86"/>'
        '<ellipse class="cons" cx="150" cy="248" rx="12" ry="18"/>'
        '<ellipse class="cons" cx="330" cy="248" rx="12" ry="18"/>'
        # 다리(원통)
        '<path class="cons" d="M214 312 L206 410"/>'
        '<path class="cons" d="M266 312 L274 410"/>'
        # 관절
        '<circle class="dot" cx="240" cy="138" r="4"/>'
        '<circle class="dot" cx="208" cy="236" r="4"/>'
        '<circle class="dot" cx="272" cy="236" r="4"/>'
        '<circle class="dot" cx="214" cy="312" r="4"/>'
        '<circle class="dot" cx="266" cy="312" r="4"/>'
    )
    labels = ('<text class="lbl" x="272" y="80">달걀</text>'
              '<text class="lbl" x="120" y="138">흉곽 상자</text>'
              '<text class="lbl" x="120" y="288">골반 상자</text>'
              '<text class="lbl" x="120" y="200">원통 팔</text>'
              '<text class="lbl" x="296" y="380">원통 다리</text>')
    return _svg("mannequin_blocking", guide, cons, labels,
                "디테일 전에 머리·흉곽·골반·팔다리를 상자와 원통으로 먼저 쌓기.")


# ── 6. 투시 격자 (2점) ─────────────────────────────────────────────────────
def perspective_grid():
    hz = 190                 # 지평선(눈높이)
    vpl, vpr = (28, hz), (452, hz)
    # 박스 앞모서리
    fx = 240
    ft, fb = 150, 300        # 앞모서리 위/아래
    guide = ''
    def to(p, q):  # 선
        return f'<line class="consd" x1="{p[0]:.0f}" y1="{p[1]:.0f}" x2="{q[0]:.0f}" y2="{q[1]:.0f}"/>'
    # 앞 수직 모서리
    cons = f'<line class="cons" x1="{fx}" y1="{ft}" x2="{fx}" y2="{fb}"/>'
    # 지평선
    cons += f'<line class="acc" x1="20" y1="{hz}" x2="460" y2="{hz}"/>'
    # 소실점
    cons += (f'<circle class="adot" cx="{vpl[0]}" cy="{vpl[1]}" r="5"/>'
             f'<circle class="adot" cx="{vpr[0]}" cy="{vpr[1]}" r="5"/>')
    # 앞모서리 → 양 소실점(위/아래)
    for y in (ft, fb):
        cons += to((fx, y), vpl) + to((fx, y), vpr)
    # 좌/우 뒤 수직 모서리(교차로 정해지는 위치 근사)
    lx, rx = 132, 348
    lt = ft + (hz - ft) * (fx - lx) / (fx - vpl[0])
    lb = fb + (hz - fb) * (fx - lx) / (fx - vpl[0])
    rt = ft + (hz - ft) * (rx - fx) / (vpr[0] - fx)
    rb = fb + (hz - fb) * (rx - fx) / (vpr[0] - fx)
    cons += f'<line class="cons" x1="{lx}" y1="{lt:.0f}" x2="{lx}" y2="{lb:.0f}"/>'
    cons += f'<line class="cons" x1="{rx}" y1="{rt:.0f}" x2="{rx}" y2="{rb:.0f}"/>'
    labels = (f'<text class="lbl" x="{vpl[0]}" y="{hz-12}">소실점</text>'
              f'<text class="lbl" x="{vpr[0]-44}" y="{hz-12}">소실점</text>'
              f'<text class="lbl" x="22" y="{hz+22}" fill="{ACC}">지평선 = 눈높이</text>'
              f'<text class="lbl" x="{fx+8}" y="{ft-8}">앞모서리</text>')
    return _svg("perspective_grid", guide, cons, labels,
                "눈높이(지평선)를 먼저 긋고, 모든 면을 소실점으로 모은다.")


# ── 7. 빛 용어 한 장 (구) ──────────────────────────────────────────────────
def form_shadow_terms():
    cx, cy, r = 230, 215, 110
    defs = ('<defs><radialGradient id="sph" cx="38%" cy="34%" r="75%">'
            '<stop offset="0%" stop-color="#f3f3f3"/>'
            '<stop offset="48%" stop-color="#b9bdc4"/>'
            '<stop offset="74%" stop-color="#4c5057"/>'
            '<stop offset="86%" stop-color="#33373d"/>'
            '<stop offset="100%" stop-color="#5b5f66"/>'   # 반사광으로 살짝 밝아짐
            '</radialGradient></defs>')
    guide = f'<circle class="guide" cx="{cx}" cy="{cy}" r="{r}"/>'
    cons = (
        _arrow(70, 70, 150, 150, "acc")                                   # 광원
        + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#sph)"/>'
        + f'<ellipse cx="{cx+95}" cy="{cy+135}" rx="120" ry="26" fill="#33373d" opacity=".30"/>'  # 캐스트
        + f'<ellipse cx="{cx+8}" cy="{cy+r-6}" rx="44" ry="12" fill="#26292e" opacity=".55"/>'     # 오클루전
        + f'<circle cx="{cx-38}" cy="{cy-44}" r="14" fill="#f6f6f6"/>'                              # 하이라이트
        # 코어 그림자(명암경계) 호
        + f'<path d="M{cx-78} {cy+74} A{r} {r} 0 0 1 {cx+70} {cy-82}" '
          'fill="none" stroke="#2b2e33" stroke-width="6" opacity=".5"/>'
    )
    labels = ('<text class="lbl" x="60" y="56" fill="' + ACC + '">광원</text>'
              '<text class="lbl" x="120" y="150">하이라이트</text>'
              '<text class="lbl" x="120" y="196">중간톤</text>'
              '<text class="lbl" x="252" y="150">코어 그림자</text>'
              '<text class="lbl" x="300" y="300">반사광</text>'
              '<text class="lbl" x="300" y="360">캐스트 그림자</text>'
              '<text class="lbl" x="120" y="340">접지(오클루전)</text>')
    return _svg("form_shadow_terms", guide, cons, labels,
                "구 하나에 빛의 모든 부분: 하이라이트·중간톤·코어그림자·반사광·캐스트·접지.",
                defs=defs)


# ── 8. 모서리 조절 (단단/부드러움/잃은) ────────────────────────────────────
def edge_control():
    defs = ('<defs><linearGradient id="soft" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0%" stop-color="#33373d"/><stop offset="100%" stop-color="#e9eaec"/>'
            '</linearGradient>'
            '<linearGradient id="lost" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#9aa0a8"/><stop offset="100%" stop-color="#cfd3d8"/>'
            '</linearGradient></defs>')
    bg = '<rect x="60" y="70" width="360" height="300" rx="10" fill="#cfd3d8"/>'
    guide = bg
    cons = (
        # 단단한 모서리: 또렷한 경계
        '<path d="M120 110 a70 70 0 0 1 0 200 Z" fill="#33373d"/>'
        '<path class="cons" d="M120 110 a70 70 0 0 1 0 200" stroke-width="2"/>'
        # 부드러운 모서리: 그라데이션
        '<rect x="200" y="120" width="90" height="180" rx="44" fill="url(#soft)"/>'
        # 잃은 모서리: 배경과 같은 값으로 녹음
        '<path d="M330 130 q60 20 50 90 q-8 70 -64 78 q-30 4 -36 -10" fill="url(#lost)"/>'
    )
    labels = ('<text class="lbl" x="92" y="350">단단한 모서리</text>'
              '<text class="lbl" x="206" y="350">부드러운 모서리</text>'
              '<text class="lbl" x="326" y="350">잃은 모서리</text>')
    return _svg("edge_control", guide, cons, labels,
                "같은 형태도 모서리를 단단히·부드럽게·잃게 해 입체와 초점을 만든다.",
                defs=defs)


# ── 9. 색상환 (12색 + 보색/유사색) ─────────────────────────────────────────
def color_wheel():
    cx, cy, ri, ro = 232, 220, 64, 150
    n = 12
    wedges = ""
    for i in range(n):
        a0 = math.radians(-90 + 360 * i / n)
        a1 = math.radians(-90 + 360 * (i + 1) / n)
        rr, gg, bb = colorsys.hsv_to_rgb(i / n, 0.62, 0.92)
        col = "#%02x%02x%02x" % (int(rr * 255), int(gg * 255), int(bb * 255))
        p1 = (cx + ro * math.cos(a0), cy + ro * math.sin(a0))
        p2 = (cx + ro * math.cos(a1), cy + ro * math.sin(a1))
        p3 = (cx + ri * math.cos(a1), cy + ri * math.sin(a1))
        p4 = (cx + ri * math.cos(a0), cy + ri * math.sin(a0))
        wedges += (f'<path d="M{p1[0]:.1f} {p1[1]:.1f} A{ro} {ro} 0 0 1 {p2[0]:.1f} {p2[1]:.1f} '
                   f'L{p3[0]:.1f} {p3[1]:.1f} A{ri} {ri} 0 0 0 {p4[0]:.1f} {p4[1]:.1f} Z" '
                   f'fill="{col}"/>')
    guide = ''
    def mid(i, rad):
        a = math.radians(-90 + 360 * (i + 0.5) / n)
        return (cx + rad * math.cos(a), cy + rad * math.sin(a))
    # 보색: 0(빨강) ↔ 6(청록)
    c0, c6 = mid(0, ro + 6), mid(6, ro + 6)
    # 유사색: 2,3,4 묶음 호
    a_s = math.radians(-90 + 360 * 1.9 / n)
    a_e = math.radians(-90 + 360 * 5.1 / n)
    ar = ro + 18
    arc = (f'M{cx+ar*math.cos(a_s):.1f} {cy+ar*math.sin(a_s):.1f} '
           f'A{ar} {ar} 0 0 1 {cx+ar*math.cos(a_e):.1f} {cy+ar*math.sin(a_e):.1f}')
    cons = (wedges
            + f'<line class="cons" x1="{c0[0]:.1f}" y1="{c0[1]:.1f}" x2="{c6[0]:.1f}" y2="{c6[1]:.1f}"/>'
            + f'<circle class="dot" cx="{c0[0]:.1f}" cy="{c0[1]:.1f}" r="5"/>'
            + f'<circle class="dot" cx="{c6[0]:.1f}" cy="{c6[1]:.1f}" r="5"/>'
            + f'<path class="acc" d="{arc}"/>')
    labels = (f'<text class="lbl" x="{c0[0]+8:.0f}" y="{c0[1]-6:.0f}">보색</text>'
              f'<text class="lbl" x="{cx+ar:.0f}" y="{cy+10:.0f}" fill="{ACC}">유사색</text>')
    return _svg("color_wheel", guide, cons, labels,
                "색상환: 마주 보면 보색(강한 대비), 이웃하면 유사색(통일감).")


# ── 10. 노탄 매스 (2값 묶기) ───────────────────────────────────────────────
def notan_massing():
    # 왼: 흩어진 값(약함) / 오: 큰 덩어리로 묶음(강함)
    bw, bh = 170, 200
    lx, rx, ty = 40, 270, 80
    def frame(x):
        return f'<rect x="{x}" y="{ty}" width="{bw}" height="{bh}" fill="#ededed" stroke="{INK}" stroke-width="1.5"/>'
    # 왼쪽: 점점이 흩어진 어둠
    scatter = frame(lx)
    for (dx, dy, r) in [(40, 50, 16), (120, 36, 12), (30, 130, 14), (110, 150, 18), (70, 100, 10)]:
        scatter += f'<circle cx="{lx+dx}" cy="{ty+dy}" r="{r}" fill="#33373d"/>'
    # 오른쪽: 큰 덩어리 두 개로 묶음
    grouped = frame(rx)
    grouped += (f'<path d="M{rx} {ty+70} Q{rx+70} {ty+30} {rx+120} {ty+90} '
                f'L{rx+120} {ty+bh} L{rx} {ty+bh} Z" fill="#33373d"/>')
    grouped += f'<circle cx="{rx+140}" cy="{ty+48}" r="26" fill="#33373d"/>'
    guide = ''
    cons = scatter + grouped
    labels = (f'<text class="lbl" x="{lx}" y="{ty-14}">흩어진 값 · 약함</text>'
              f'<text class="lbl" x="{rx}" y="{ty-14}">덩어리로 묶음 · 강함</text>'
              f'<text class="lbl" x="{lx+40}" y="{ty+bh+34}" fill="{CONS}">→</text>'
              f'<text class="lbl" x="{lx+60}" y="{ty+bh+34}">큰 명암 덩어리부터</text>')
    return _svg("notan_massing", guide, cons, labels,
                "명암을 큰 덩어리로 묶어(노탄) 화면의 무게 균형을 먼저 본다.")


DK = "#33373d"   # 실루엣/면 어둠


# ── 11. 손 평면·마디 (hand) ────────────────────────────────────────────────
def hand_planes():
    guide = '<path class="gfill" d="M150 322 L312 322 L296 178 L166 178 Z"/>'
    cons = '<path class="cons" d="M160 322 L300 322 L288 188 L172 188 Z"/>'           # 손등 평면
    cons += '<path class="consd" d="M172 200 Q230 170 288 200"/>'                      # 너클 아치
    fx, tips = [190, 220, 250, 280], [88, 70, 80, 106]
    base = 192
    for x, ty in zip(fx, tips):
        cons += f'<line class="cons" x1="{x}" y1="{base}" x2="{x}" y2="{ty}"/>'
        seg = (base - ty) / 3
        for k in (1, 2):
            yy = base - seg * k
            cons += f'<line class="consd" x1="{x-9}" y1="{yy:.0f}" x2="{x+9}" y2="{yy:.0f}"/>'
    cons += '<path class="cons" d="M162 300 q-46 -4 -66 -38 q-10 -18 7 -30 q18 -10 31 9 l32 42"/>'  # 엄지
    cons += _arrow(232, 258, 214, 226, "acc")                                          # 평면 방향
    labels = ('<text class="lbl" x="312" y="262">손등 평면</text>'
              '<text class="lbl" x="296" y="168">너클 아치</text>'
              '<text class="lbl" x="296" y="118">마디 3칸</text>'
              '<text class="lbl" x="74" y="252">엄지</text>'
              '<text class="lbl" x="190" y="244" fill="' + ACC + '">평면 방향</text>')
    return _svg("hand_planes", guide, cons, labels,
                "손등은 한 평면, 너클은 아치. 손가락은 마디 3칸으로.")


# ── 12. 발 구조 (옆면 쐐기) ────────────────────────────────────────────────
def foot_structure():
    outline = ("M170 360 L174 302 Q180 252 212 250 L232 252 "
               "Q272 272 320 346 L360 348 L362 360 Q255 346 196 360 Z")
    guide = f'<path class="gfill" d="{outline}"/>'
    cons = (f'<path class="cons" d="{outline}"/>'
            '<circle class="cons" cx="212" cy="240" r="26"/>'          # 발목 공
            '<line class="consd" x1="320" y1="346" x2="362" y2="350"/>'  # 발가락 칸 구분
            '<line class="consd" x1="336" y1="346" x2="338" y2="360"/>'
            '<path class="acc" d="M196 360 Q250 340 320 350"/>')        # 아치(들린 안쪽)
    labels = ('<text class="lbl" x="240" y="232">발목(공)</text>'
              '<text class="lbl" x="244" y="300">발등 경사</text>'
              '<text class="lbl" x="316" y="332">발가락 상자</text>'
              '<text class="lbl" x="92" y="318">발꿈치</text>'
              '<text class="lbl" x="226" y="392" fill="' + ACC + '">아치(살짝 들림)</text>')
    return _svg("foot_structure", guide, cons, labels,
                "발 = 쐐기 덩어리 + 발목 공. 안쪽 아치는 바닥에서 살짝 들린다.")


# ── 13. 머리 각도 (들기·숙이기) ────────────────────────────────────────────
def head_angles():
    def head(cx, cy, d):
        r = 50
        jaw = (f'<path class="cons" d="M{cx-r} {cy+6} C{cx-r} {cy+r+18} {cx-22} {cy+r+34} '
               f'{cx} {cy+r+34} C{cx+22} {cy+r+34} {cx+r} {cy+r+18} {cx+r} {cy+6}"/>')
        s = f'<circle class="cons" cx="{cx}" cy="{cy}" r="{r}"/>' + jaw
        s += f'<line class="acc" x1="{cx}" y1="{cy-r-4}" x2="{cx}" y2="{cy+r+34}"/>'   # 중심선
        # 가로 특징선(눈썹·코·입)이 d만큼 휜다
        for off in (10, 40, 66):
            yy = cy + off
            s += (f'<path class="consd" d="M{cx-r+6} {yy} Q{cx} {yy+d} {cx+r-6} {yy}"/>')
        return s
    cons = head(110, 190, 16) + head(240, 190, 0) + head(370, 190, -16)
    labels = ('<text class="lbl" x="110" y="312" text-anchor="middle">내려봄</text>'
              '<text class="lbl" x="240" y="312" text-anchor="middle">정면</text>'
              '<text class="lbl" x="370" y="312" text-anchor="middle">올려봄</text>')
    return _svg("head_angles", '', cons, labels,
                "고개를 숙이고 들면 눈썹·코·입 가로선이 아래/위로 휜다.")


# ── 14. 명도 자 (9단) ──────────────────────────────────────────────────────
def value_scale():
    n = 9
    x0, y0, w, h, gap = 46, 110, 40, 110, 4
    cons = ""
    for i in range(n):
        v = 1 - i / (n - 1)
        g = int(round(v * 255))
        x = x0 + i * (w + gap)
        cons += f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" fill="#{g:02x}{g:02x}{g:02x}" stroke="{INK}" stroke-width="1.2"/>'
        cons += f'<text class="tag" x="{x+w/2:.0f}" y="{y0+h+18}" text-anchor="middle">{i+1}</text>'
    # 콜아웃: 하이라이트(2) · 중간(4) · 코어(7)
    def cell(i):
        return x0 + i * (w + gap) + w / 2
    for i, name in [(1, "하이라이트"), (3, "중간톤"), (6, "코어")]:
        cx = cell(i)
        cons += _arrow(cx, y0 - 30, cx, y0 - 6, "acc")
        cons += f'<text class="lbl" x="{cx:.0f}" y="{y0-36}" text-anchor="middle" fill="{ACC}">{name}</text>'
    labels = (f'<text class="lbl" x="{x0}" y="{y0+h+48}">밝음</text>'
              f'<text class="lbl" x="{x0+(n-1)*(w+gap)+w-32:.0f}" y="{y0+h+48}">어둠</text>')
    return _svg("value_scale", '', cons, labels,
                "9단 명도 자: 양 끝(흰·검)은 아끼고 큰 형태는 3~4단으로.")


# ── 15. 면과 명도 (planes of form) ─────────────────────────────────────────
def planes_of_form():
    defs = ('<defs><linearGradient id="cyl" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0%" stop-color="#e7e8ea"/><stop offset="42%" stop-color="#b6bac1"/>'
            '<stop offset="74%" stop-color="#5b5f66"/><stop offset="90%" stop-color="#3a3e44"/>'
            '<stop offset="100%" stop-color="#7e828a"/></linearGradient></defs>')
    cons = _arrow(70, 70, 132, 124, "acc")
    # 큐브(윗면 밝음·앞면 중간·옆면 어둠)
    cons += ('<polygon points="96,210 176,210 216,180 136,180" fill="#e7e8ea" stroke="' + INK + '"/>'
             '<polygon points="96,210 176,210 176,312 96,312" fill="#b6bac1" stroke="' + INK + '"/>'
             '<polygon points="176,210 216,180 216,282 176,312" fill="#5b5f66" stroke="' + INK + '"/>')
    # 원기둥(면이 둥글게 도는 명도)
    cons += ('<ellipse cx="330" cy="196" rx="56" ry="18" fill="#eceded" stroke="' + INK + '"/>'
             '<path d="M274 196 L274 320 A56 18 0 0 0 386 320 L386 196" fill="url(#cyl)" stroke="' + INK + '"/>'
             '<path d="M274 320 A56 18 0 0 0 386 320" fill="none" stroke="' + INK + '"/>')
    labels = ('<text class="lbl" x="150" y="172">윗면 밝음</text>'
              '<text class="lbl" x="40" y="270">앞면 중간</text>'
              '<text class="lbl" x="222" y="250">옆면 어둠</text>'
              '<text class="lbl" x="296" y="180">둥근 면은 부드럽게</text>')
    return _svg("planes_of_form", '', cons, labels,
                "면이 꺾이는 곳에서 명도가 바뀐다 — 윗면 밝게, 옆면 어둡게.",
                defs=defs)


# ── 16. 1점 투시 ───────────────────────────────────────────────────────────
def one_point_perspective():
    hz, vp = 188, (240, 188)
    TL, TR, BL, BR = (150, 214), (250, 214), (150, 304), (250, 304)
    def lerp(p, t):
        return (p[0] + (vp[0] - p[0]) * t, p[1] + (vp[1] - p[1]) * t)
    bTL, bTR = lerp(TL, 0.5), lerp(TR, 0.5)
    guide = ''
    cons = f'<line class="acc" x1="20" y1="{hz}" x2="460" y2="{hz}"/>'
    cons += f'<circle class="adot" cx="{vp[0]}" cy="{vp[1]}" r="5"/>'
    # 앞면(화면과 평행)
    cons += f'<rect class="cons" x="{TL[0]}" y="{TL[1]}" width="{TR[0]-TL[0]}" height="{BL[1]-TL[1]}"/>'
    # 윗면(소실점으로)
    cons += (f'<path class="cons" d="M{TL[0]} {TL[1]} L{bTL[0]:.0f} {bTL[1]:.0f} '
             f'L{bTR[0]:.0f} {bTR[1]:.0f} L{TR[0]} {TR[1]}"/>')
    for p in (TL, TR, BL, BR):
        cons += f'<line class="consd" x1="{p[0]}" y1="{p[1]}" x2="{vp[0]}" y2="{vp[1]}"/>'
    labels = (f'<text class="lbl" x="{vp[0]+10}" y="{hz-10}">소실점 1개</text>'
              f'<text class="lbl" x="22" y="{hz+22}" fill="{ACC}">지평선 = 눈높이</text>'
              f'<text class="lbl" x="96" y="350">앞면은 화면과 평행</text>')
    return _svg("one_point_perspective", guide, cons, labels,
                "소실점 하나. 깊이로 가는 선만 그 점으로, 앞면은 화면과 평행.")


# ── 17. 타원 투시 (원기둥) ─────────────────────────────────────────────────
def ellipse_perspective():
    cx = 250
    cons = ('<line class="accd" x1="' + str(cx) + '" y1="120" x2="' + str(cx) + '" y2="392"/>'   # 중심축=단축
            f'<ellipse class="cons" cx="{cx}" cy="150" rx="82" ry="26"/>'
            f'<ellipse class="cons" cx="{cx}" cy="362" rx="82" ry="34"/>'
            f'<line class="cons" x1="{cx-82}" y1="150" x2="{cx-82}" y2="362"/>'
            f'<line class="cons" x1="{cx+82}" y1="150" x2="{cx+82}" y2="362"/>'
            # 장축(가로) 표시
            f'<line class="acc" x1="{cx-82}" y1="150" x2="{cx+82}" y2="150"/>')
    # 눈높이에서 멀수록 더 벌어지는 타원 스택(왼쪽)
    for i, ry in enumerate((4, 12, 22)):
        cons += f'<ellipse class="consd" cx="86" cy="{150+i*90}" rx="44" ry="{ry}"/>'
    labels = (f'<text class="lbl" x="{cx-8}" y="248" text-anchor="end" fill="{ACC}">중심축 = 단축</text>'
              f'<text class="lbl" x="{cx+90}" y="146">장축 ⟂ 축</text>'
              '<text class="lbl" x="40" y="120">눈높이</text>'
              '<text class="lbl" x="40" y="372">멀수록 ↑</text>')
    return _svg("ellipse_perspective", '', cons, labels,
                "원은 시점에서 타원이 된다. 단축은 중심축과 나란히, 멀수록 더 벌어진다.")


# ── 18. 색 온도 ────────────────────────────────────────────────────────────
def color_temperature():
    defs = ('<defs>'
            '<linearGradient id="warm" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0%" stop-color="#e23b2e"/><stop offset="100%" stop-color="#f2b134"/></linearGradient>'
            '<linearGradient id="cool" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0%" stop-color="#3fa86a"/><stop offset="100%" stop-color="#3157c4"/></linearGradient>'
            '<radialGradient id="lit" cx="36%" cy="32%" r="78%">'
            '<stop offset="0%" stop-color="#ffd9a0"/><stop offset="45%" stop-color="#e08a4a"/>'
            '<stop offset="100%" stop-color="#5a4a6e"/></radialGradient>'
            '</defs>')
    cons = ('<rect x="48" y="86" width="184" height="48" rx="6" fill="url(#warm)"/>'
            '<rect x="248" y="86" width="184" height="48" rx="6" fill="url(#cool)"/>')
    cons += _arrow(96, 196, 156, 244, "acc")
    cons += ('<circle cx="232" cy="304" r="84" fill="url(#lit)"/>'
             '<path d="M232 220 A84 84 0 0 0 232 388 A56 56 0 0 0 232 220 Z" fill="#2f3f6b" opacity=".4"/>'
             '<ellipse cx="312" cy="404" rx="86" ry="18" fill="#33373d" opacity=".28"/>')
    labels = ('<text class="lbl" x="80" y="78">따뜻함</text>'
              '<text class="lbl" x="300" y="78">차가움</text>'
              '<text class="lbl" x="64" y="196" fill="' + ACC + '">따뜻한 빛</text>'
              '<text class="lbl" x="300" y="300">차가운 그림자</text>')
    return _svg("color_temperature", '', cons, labels,
                "빛이 따뜻하면 그림자는 차갑게(또는 반대로) — 온도 대비로 입체감.",
                defs=defs)


# ── 19. 유도선 (시선 이끌기) ───────────────────────────────────────────────
def leading_lines():
    fx, fy, fw, fh = 40, 60, 400, 340
    fpx, fpy = fx + fw * 2 / 3, fy + fh / 3        # 3분할 교점
    guide = f'<rect class="guide" x="{fx}" y="{fy}" width="{fw}" height="{fh}"/>'
    cons = ''
    # 길(아래에서 초점으로 모이는 두 선)
    cons += f'<line class="cons" x1="{fx+70}" y1="{fy+fh}" x2="{fpx:.0f}" y2="{fpy:.0f}"/>'
    cons += f'<line class="cons" x1="{fx+fw-40}" y1="{fy+fh}" x2="{fpx:.0f}" y2="{fpy:.0f}"/>'
    # 보조 유도선(좌측 능선)
    cons += f'<path class="consd" d="M{fx} {fy+fh-40} Q{fx+140} {fpy+80:.0f} {fpx:.0f} {fpy:.0f}"/>'
    # 시선 화살표
    cons += _arrow(fx + 70, fy + 90, fpx - 16, fpy - 6, "acc")
    cons += f'<circle class="dot" cx="{fpx:.0f}" cy="{fpy:.0f}" r="13"/>'
    # 3분할 격자(연하게)
    for i in (1, 2):
        cons += f'<line class="consd" x1="{fx+fw*i/3:.0f}" y1="{fy}" x2="{fx+fw*i/3:.0f}" y2="{fy+fh}" opacity=".5"/>'
        cons += f'<line class="consd" x1="{fx}" y1="{fy+fh*i/3:.0f}" x2="{fx+fw}" y2="{fy+fh*i/3:.0f}" opacity=".5"/>'
    labels = (f'<text class="lbl" x="{fpx+18:.0f}" y="{fpy+5:.0f}">초점</text>'
              f'<text class="lbl" x="{fx+90}" y="{fy+fh-12}">유도선</text>'
              f'<text class="lbl" x="{fx+50}" y="{fy+86}" fill="{ACC}">시선</text>')
    return _svg("leading_lines", guide, cons, labels,
                "선·길·시선이 한 점(초점)으로 모이게 해 시선을 이끈다.")


# ── 20. 실루엣 가독성 ──────────────────────────────────────────────────────
def silhouette_read():
    guide = ('<rect class="gfill" x="40" y="70" width="180" height="320"/>'
             '<rect class="gfill" x="260" y="70" width="180" height="320"/>')
    # 읽히는 실루엣(팔다리 벌림)
    clear = (f'<circle cx="128" cy="116" r="22" fill="{DK}"/>'
             f'<path d="M110 138 L146 138 L156 250 L138 256 L128 200 L118 256 L100 250 Z" fill="{DK}"/>'
             f'<path d="M114 150 L70 120 L60 132 L104 168 Z" fill="{DK}"/>'        # 한 팔 위로
             f'<path d="M142 150 L188 196 L178 208 L132 172 Z" fill="{DK}"/>'      # 한 팔 아래로
             f'<path d="M122 250 L108 360 L96 360 L114 252 Z" fill="{DK}"/>'       # 다리 벌림
             f'<path d="M134 252 L160 356 L148 360 L126 254 Z" fill="{DK}"/>')
    # 안 읽히는 실루엣(다 붙음 → 덩어리)
    blob = (f'<circle cx="350" cy="116" r="22" fill="{DK}"/>'
            f'<path d="M316 138 L384 138 L392 300 L356 372 L348 372 L308 300 Z" fill="{DK}"/>')
    cons = clear + blob
    labels = ('<text class="lbl" x="56" y="62">읽힘 (틈이 보임)</text>'
              '<text class="lbl" x="276" y="62">안 읽힘 (덩어리)</text>'
              '<text class="lbl" x="60" y="384" fill="' + CONS + '">팔다리 사이 음형</text>')
    return _svg("silhouette_read", guide, cons, labels,
                "실루엣만 검게 채워 보기 — 팔다리 사이 틈(음형)이 보여야 읽힌다.")


DIAGRAMS = {
    "head_construction": head_construction,
    "facial_proportion": facial_proportion,
    "torso_box": torso_box,
    "gesture_rhythm": gesture_rhythm,
    "mannequin_blocking": mannequin_blocking,
    "perspective_grid": perspective_grid,
    "form_shadow_terms": form_shadow_terms,
    "edge_control": edge_control,
    "color_wheel": color_wheel,
    "notan_massing": notan_massing,
    "hand_planes": hand_planes,
    "foot_structure": foot_structure,
    "head_angles": head_angles,
    "value_scale": value_scale,
    "planes_of_form": planes_of_form,
    "one_point_perspective": one_point_perspective,
    "ellipse_perspective": ellipse_perspective,
    "color_temperature": color_temperature,
    "leading_lines": leading_lines,
    "silhouette_read": silhouette_read,
}

# 각 도식이 받치는 taxonomy 축(sub_problem) + 페르소나 — run_guide(asset_index=...) 인덱싱용.
MANIFEST = {
    "head_construction": {"supports": ["proportion"], "personas": ["anatomy", "pose"],
                          "caption": "머리통(공)+턱 + 얼굴 3등분."},
    "facial_proportion": {"supports": ["proportion"], "personas": ["anatomy"],
                          "caption": "눈은 머리 높이 정중앙, 얼굴=눈 5칸."},
    "torso_box": {"supports": ["weight_balance", "proportion"], "personas": ["anatomy", "pose"],
                  "caption": "흉곽·골반 두 상자와 척추의 비틀림."},
    "gesture_rhythm": {"supports": ["action_line"], "personas": ["pose"],
                       "caption": "C·S·I 선과 직선 대 곡선 리듬."},
    "mannequin_blocking": {"supports": ["proportion", "weight_balance", "joint_articulation"],
                           "personas": ["pose", "anatomy"],
                           "caption": "상자·원통으로 전신 블로킹."},
    "perspective_grid": {"supports": ["foreshortening"], "personas": ["perspective"],
                         "caption": "지평선(눈높이)+소실점 2점 투시."},
    "form_shadow_terms": {"supports": ["light_direction", "value_structure"],
                          "personas": ["light", "technique"],
                          "caption": "구 한 장에 빛 용어 전체."},
    "edge_control": {"supports": ["value_structure"], "personas": ["technique"],
                     "caption": "단단·부드러움·잃은 모서리."},
    "color_wheel": {"supports": ["color_harmony"], "personas": ["color"],
                    "caption": "12색 색상환 + 보색·유사색."},
    "notan_massing": {"supports": ["composition_balance", "value_structure"],
                      "personas": ["composition", "light"],
                      "caption": "2값 노탄으로 큰 덩어리 묶기."},
    "hand_planes": {"supports": ["hand_structure"], "personas": ["hand", "anatomy"],
                    "caption": "손등 평면 + 너클 아치 + 마디 3칸."},
    "foot_structure": {"supports": ["proportion", "weight_balance"], "personas": ["anatomy", "pose"],
                       "caption": "발 = 쐐기 + 발목 공, 안쪽 아치."},
    "head_angles": {"supports": ["proportion", "foreshortening"], "personas": ["anatomy"],
                    "caption": "고개 들기·숙이기로 가로선이 휜다."},
    "value_scale": {"supports": ["value_structure"], "personas": ["light", "technique"],
                    "caption": "9단 명도 자."},
    "planes_of_form": {"supports": ["value_structure", "light_direction"],
                       "personas": ["light", "anatomy", "technique"],
                       "caption": "면이 꺾이면 명도가 바뀐다(큐브·원기둥)."},
    "one_point_perspective": {"supports": ["foreshortening"], "personas": ["perspective"],
                              "caption": "소실점 1개 투시."},
    "ellipse_perspective": {"supports": ["foreshortening"], "personas": ["perspective", "anatomy"],
                            "caption": "원기둥의 타원 — 단축은 중심축."},
    "color_temperature": {"supports": ["color_harmony"], "personas": ["color", "light"],
                          "caption": "따뜻한 빛 / 차가운 그림자."},
    "leading_lines": {"supports": ["composition_balance"], "personas": ["composition"],
                      "caption": "유도선으로 시선을 초점으로."},
    "silhouette_read": {"supports": ["action_line", "composition_balance"],
                        "personas": ["pose", "composition"],
                        "caption": "실루엣 가독성 · 음형."},
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "reference"
    os.makedirs(out, exist_ok=True)
    for name, fn in DIAGRAMS.items():
        path = os.path.join(out, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn())
        print("wrote", path)
    # manifest: sub_problem -> [{type:svg, ref_id, label, caption, personas}]
    index = {}
    for name, meta in MANIFEST.items():
        for sp in meta["supports"]:
            index.setdefault(sp, []).append({
                "type": "svg", "ref_id": f"reference/{name}.svg",
                "label": "도식", "caption": meta["caption"], "personas": meta["personas"],
            })
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"diagrams": MANIFEST, "asset_index": index}, f, ensure_ascii=False, indent=2)
    print("wrote", os.path.join(out, "manifest.json"))
    print(f"\n{len(DIAGRAMS)}개 레퍼런스 도식 생성 완료 → {out}/")


if __name__ == "__main__":
    main()
