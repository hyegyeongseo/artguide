"""gen_construction_diagrams.py — taxonomy 10개 축의 '구축 다이어그램' SVG 생성기.

각 sub_problem마다 교육용 도식(추상 기하)을 한 장씩 만든다. 사실적 인체가 아니라
'어떻게 생각하라'를 보여주는 단순화 도형이라 구성상 정확(correct-by-construction).
레이어를 <g id="construction"> / <g id="guide"> / <g id="label">로 분리해 두어
프론트에서 토글(구축선만/외곽만/라벨만)할 수 있다.

사실적 포즈별 윤곽선은 별개(Blender Freestyle 3D→SVG, render/freestyle_svg.py).
이건 포즈에 안 묶인 '일반 교육 다이어그램'이다.

실행:  python tools/gen_construction_diagrams.py [out_dir]
출력:  <out_dir>/<sub_problem>.svg  (기본 out_dir = ./construction)
"""
import os
import sys

W = H = 480
GUIDE = "#c7ccd4"      # 연한 가이드(형태)
CONS = "#e0533d"       # 구축선(빨강-주황)
ACC = "#2f6df0"        # 강조(파랑) — 드물게
INK = "#3a3f47"        # 라벨 텍스트
DASH = "6 5"


def _svg(title, body_guide, body_cons, labels, caption):
    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">
  <style>
    .guide {{ fill:none; stroke:{GUIDE}; stroke-width:2.5; }}
    .gfill {{ fill:{GUIDE}; opacity:.18; stroke:none; }}
    .cons  {{ fill:none; stroke:{CONS}; stroke-width:2.5; stroke-linecap:round; stroke-linejoin:round; }}
    .consd {{ fill:none; stroke:{CONS}; stroke-width:2; stroke-dasharray:{DASH}; }}
    .acc   {{ fill:none; stroke:{ACC};  stroke-width:2.5; stroke-linecap:round; }}
    .dot   {{ fill:{CONS}; stroke:none; }}
    .lbl   {{ fill:{INK}; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif; font-size:14px; }}
    .cap   {{ fill:{INK}; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif; font-size:13px; opacity:.8; }}
    .tag   {{ fill:{CONS}; font-family:sans-serif; font-size:12px; font-weight:600; }}
  </style>
  <g id="guide">{body_guide}</g>
  <g id="construction">{body_cons}</g>
  <g id="label">{labels}
    <text class="cap" x="20" y="{H-18}">{caption}</text>
  </g>
</svg>
"""


def _circles_ruler(x, top, unit, n):
    """머리 단위 자(세로로 쌓인 원)."""
    s = ""
    for i in range(n):
        cy = top + unit * i + unit / 2
        s += f'<circle class="consd" cx="{x}" cy="{cy:.1f}" r="{unit/2:.1f}"/>'
        s += f'<text class="tag" x="{x-4}" y="{cy+4:.1f}" text-anchor="middle">{i}</text>'
    return s


# ── 축별 다이어그램 ────────────────────────────────────────────────────────
def hand_structure():
    # 손바닥 = 상자(평행사변형), 손가락 = 원통, 엄지 별도. '벙어리장갑' 단순화.
    guide = ('<path class="guide" d="M180 250 q-15 -70 25 -120 q35 -40 70 -10 '
             'q20 -50 45 -20 q18 -45 38 -12 q22 -35 30 5 q26 30 -8 90 '
             'q-30 60 -95 70 q-70 8 -105 -3 Z"/>')
    cons = (
        # 손바닥 상자
        '<path class="cons" d="M175 250 L205 150 L300 165 L285 270 Z"/>'
        # 손가락 원통 4개
        '<path class="cons" d="M205 150 q12 -55 30 -50 q14 4 8 56"/>'
        '<path class="cons" d="M238 150 q14 -62 32 -56 q14 4 6 62"/>'
        '<path class="cons" d="M270 156 q14 -52 30 -44 q12 6 4 56"/>'
        '<path class="cons" d="M295 165 q12 -38 26 -30 q10 6 2 44"/>'
        # 엄지 원통
        '<path class="cons" d="M175 250 q-44 4 -58 40 q-6 18 14 24 q22 4 40 -24"/>'
        # 평면 방향 화살표(손등이 향하는 쪽)
        '<path class="acc" d="M235 205 l60 -22"/>'
        '<path class="acc" d="M289 178 l8 5 l-9 4"/>'
    )
    labels = ('<text class="lbl" x="300" y="250">손바닥 = 상자</text>'
              '<text class="lbl" x="250" y="95">손가락 = 원통</text>'
              '<text class="lbl" x="300" y="170" fill="'+ACC+'">평면 방향</text>')
    return _svg("hand_structure", guide, cons, labels,
                "손 = 손바닥(상자) + 손가락(원통). 먼저 평면 방향부터.")


def proportion():
    top, foot, x = 60, 420, 250
    n = 8
    unit = (foot - top) / n
    guide = (f'<line class="guide" x1="{x}" y1="{top}" x2="{x}" y2="{foot}"/>')
    # 가로 기준선
    marks = {0: "머리", 1: "턱", 2: "가슴", 3: "허리", 4: "골반", 6: "무릎", 8: "발"}
    cons = ""
    for u, name in marks.items():
        y = top + unit * u
        cons += f'<line class="consd" x1="{x-90}" y1="{y:.1f}" x2="{x+90}" y2="{y:.1f}"/>'
    # 간단한 인물 실루엣(가이드)
    guide += (f'<circle class="gfill" cx="{x}" cy="{top+unit/2:.0f}" r="{unit/2:.0f}"/>'
              f'<path class="gfill" d="M{x-40} {top+unit*2:.0f} q40 -25 80 0 '
              f'l-12 {unit*2.4:.0f} l8 {unit*3.4:.0f} l-22 0 l-12 -{unit*2.6:.0f} '
              f'l-12 {unit*2.6:.0f} l-22 0 l8 -{unit*3.4:.0f} Z"/>')
    labels = _circles_ruler(x + 120, top, unit, n)
    for u, name in marks.items():
        y = top + unit * u
        labels += f'<text class="lbl" x="{x-150}" y="{y+4:.1f}">{name}</text>'
    return _svg("proportion", guide, cons, labels,
                "머리 1개를 자로 삼아 어깨·허리·무릎·발 위치를 점만 찍기.")


def weight_balance():
    # contrapposto: 어깨선/골반선 반대로 기울고, 무게중심 수직선이 지지발 위로.
    guide = ('<path class="gfill" d="M210 110 q40 -30 80 0 l-6 110 q24 80 6 200 '
             'l-26 0 l-12 -150 l-18 150 l-26 0 q18 -120 6 -200 Z"/>')
    cons = (
        '<line class="cons" x1="200" y1="150" x2="300" y2="135"/>'   # 어깨선(기움)
        '<line class="cons" x1="210" y1="250" x2="298" y2="262"/>'   # 골반선(반대로)
        '<line class="consd" x1="252" y1="120" x2="252" y2="420"/>'  # 무게중심 수직선
        '<circle class="dot" cx="252" cy="120" r="5"/>'
        '<circle class="dot" cx="252" cy="418" r="6"/>'              # 지지발
    )
    labels = ('<text class="lbl" x="305" y="139">어깨</text>'
              '<text class="lbl" x="305" y="266">골반</text>'
              '<text class="lbl" x="258" y="135">무게중심선</text>'
              '<text class="lbl" x="258" y="435">지지발</text>')
    return _svg("weight_balance", guide, cons, labels,
                "지지발을 먼저 정하고, 그 위로 머리 중심이 오게.")


def foreshortening():
    # 카메라로 뻗은 팔 = 겹치는 원통(가까운 게 크고, 먼 게 작게).
    guide = '<ellipse class="gfill" cx="250" cy="250" rx="120" ry="60"/>'
    cons = (
        '<ellipse class="cons" cx="170" cy="250" rx="62" ry="60"/>'   # 어깨쪽(큰 마디)
        '<ellipse class="cons" cx="280" cy="250" rx="40" ry="46"/>'   # 중간 마디
        '<ellipse class="cons" cx="345" cy="250" rx="24" ry="30"/>'   # 손쪽(작은 마디)
        '<path class="consd" d="M170 250 L280 250"/>'
        '<path class="consd" d="M280 250 L345 250"/>'
        '<path class="acc" d="M150 360 l210 0"/>'                     # 비교: 평평한 팔
        '<text class="tag" x="360" y="364" fill="'+ACC+'">평평(아는 대로)</text>'
    )
    labels = ('<text class="lbl" x="140" y="180">가까운 마디 크게</text>'
              '<text class="lbl" x="300" y="200">먼 마디 작게·겹침</text>')
    return _svg("foreshortening", guide, cons, labels,
                "원통 마디로: 가까운 건 크게, 먼 건 작게 겹쳐.")


def action_line():
    # 동작을 관통하는 한 곡선(S/C) + 그 위에 매스 몇 개.
    guide = ('<circle class="gfill" cx="190" cy="110" r="34"/>'
             '<ellipse class="gfill" cx="240" cy="220" rx="60" ry="80"/>'
             '<ellipse class="gfill" cx="300" cy="360" rx="34" ry="60"/>')
    cons = ('<path class="cons" d="M170 90 C 230 180, 200 280, 320 410"/>'
            '<circle class="dot" cx="170" cy="90" r="5"/>'
            '<circle class="dot" cx="320" cy="410" r="5"/>')
    labels = ('<text class="lbl" x="60" y="90">머리</text>'
              '<text class="lbl" x="330" y="410">지지발</text>'
              '<text class="lbl" x="120" y="250" fill="'+CONS+'">관통하는 한 선</text>')
    return _svg("action_line", guide, cons, labels,
                "디테일 전에 머리→지지발을 한 곡선으로 먼저.")


def joint_articulation():
    # 팔꿈치 = 위·아래 뼈(직선 둘) + 자연스러운 굽힘 범위 호.
    guide = ('<path class="gfill" d="M120 120 q40 -10 60 30 l60 120 q20 40 -10 70 '
             'q-40 20 -60 -20 l-60 -130 q-20 -40 10 -70 Z"/>')
    cons = (
        '<line class="cons" x1="140" y1="130" x2="240" y2="250"/>'   # 위팔 뼈
        '<line class="cons" x1="240" y1="250" x2="210" y2="380"/>'   # 아래팔 뼈
        '<circle class="dot" cx="240" cy="250" r="6"/>'              # 관절
        '<path class="consd" d="M275 250 A 40 40 0 0 1 240 290"/>'   # 굽힘 범위 호
    )
    labels = ('<text class="lbl" x="250" y="245">관절</text>'
              '<text class="lbl" x="150" y="185">위 뼈</text>'
              '<text class="lbl" x="120" y="340">아래 뼈</text>'
              '<text class="lbl" x="285" y="290">자연스러운 굽힘 범위</text>')
    return _svg("joint_articulation", guide, cons, labels,
                "관절 위·아래를 직선 둘로 단순화해 각도 확인.")


def value_structure():
    # 3단 명도 막대 + 3단으로 칠한 구.
    cons = ""
    vals = [("#f0f0f0", "밝음"), ("#9aa0a8", "중간"), ("#33373d", "어둠")]
    for i, (c, _) in enumerate(vals):
        cons += f'<rect x="{60+i*90}" y="60" width="80" height="80" fill="{c}" stroke="{INK}" stroke-width="1.5"/>'
    # 구: 3값 (하이라이트/코어/캐스트는 단순화)
    guide = '<circle class="guide" cx="250" cy="320" r="90"/>'
    cons += ('<path d="M250 230 A90 90 0 0 1 250 410 A90 90 0 0 1 250 230" fill="#9aa0a8"/>'
             '<path d="M250 230 A90 90 0 0 0 175 360 A70 70 0 0 0 250 392 Z" fill="#33373d" opacity=".9"/>'
             '<circle cx="290" cy="285" r="22" fill="#f4f4f4"/>'
             '<ellipse cx="290" cy="425" rx="80" ry="16" fill="#33373d" opacity=".35"/>')
    labels = ('<text class="lbl" x="60" y="175">밝음</text>'
              '<text class="lbl" x="150" y="175">중간</text>'
              '<text class="lbl" x="240" y="175">어둠</text>')
    return _svg("value_structure", '', cons, labels,
                "흑백 3단(밝음·중간·어둠)으로 나눠 빠진 단계 확인.")


def light_direction():
    # 광원 화살표 + 구의 밝은면/코어그림자/캐스트가 한 방향으로 일관.
    guide = '<circle class="guide" cx="250" cy="250" r="90"/>'
    cons = (
        '<line class="acc" x1="80" y1="90" x2="190" y2="190"/>'      # 광원 화살표
        '<path class="acc" d="M190 190 l-2 -16 m2 16 l-16 -2"/>'
        '<circle cx="225" cy="220" r="20" fill="#f4f4f4"/>'          # 하이라이트
        '<path d="M250 160 A90 90 0 0 0 250 340 A60 60 0 0 0 250 160 Z" fill="#33373d" opacity=".85"/>'
        '<ellipse cx="330" cy="360" rx="90" ry="18" fill="#33373d" opacity=".35"/>'  # 캐스트
    )
    labels = ('<text class="lbl" x="60" y="80" fill="'+ACC+'">광원</text>'
              '<text class="lbl" x="195" y="215">밝은 면</text>'
              '<text class="lbl" x="255" y="255">코어 그림자</text>'
              '<text class="lbl" x="300" y="395">캐스트 그림자</text>')
    return _svg("light_direction", guide, cons, labels,
                "광원 하나를 정하고 모든 형태의 밝은 면이 그쪽을 향하게.")


def composition_balance():
    # 3분할 격자 + 교점에 초점 + 반대편 보조 매스.
    fx, fy = 60, 60
    fw = fh = 360
    cons = f'<rect class="guide" x="{fx}" y="{fy}" width="{fw}" height="{fh}"/>'
    for i in (1, 2):
        x = fx + fw * i / 3
        y = fy + fh * i / 3
        cons += f'<line class="consd" x1="{x}" y1="{fy}" x2="{x}" y2="{fy+fh}"/>'
        cons += f'<line class="consd" x1="{fx}" y1="{y}" x2="{fx+fw}" y2="{y}"/>'
    # 초점(좌상 교점) + 보조 매스(우하)
    cons += f'<circle class="dot" cx="{fx+fw/3}" cy="{fy+fh/3}" r="14"/>'
    cons += f'<circle class="gfill" cx="{fx+fw*2/3}" cy="{fy+fh*2/3}" r="34"/>'
    labels = (f'<text class="lbl" x="{fx+fw/3+22}" y="{fy+fh/3+5}">초점(교점)</text>'
              f'<text class="lbl" x="{fx+fw*2/3-30}" y="{fy+fh*2/3+60}">균형 매스</text>')
    return _svg("composition_balance", '', cons, labels,
                "주제를 정중앙에서 한 칸 옮겨 3분할 교점에.")


def color_harmony():
    # 주조·보조·강조 스와치 + 비율 막대(제한 팔레트).
    sw = [("#3d5a73", "주조 60%"), ("#b89a6a", "보조 30%"), ("#d14b3d", "강조 10%")]
    cons = ""
    x = 60
    for c, _ in sw:
        cons += f'<rect x="{x}" y="80" width="110" height="110" rx="8" fill="{c}"/>'
        x += 130
    # 비율 막대
    cons += ('<rect x="60" y="250" width="216" height="40" fill="#3d5a73"/>'
             '<rect x="276" y="250" width="108" height="40" fill="#b89a6a"/>'
             '<rect x="384" y="250" width="36" height="40" fill="#d14b3d"/>')
    labels = ('<text class="lbl" x="60" y="215">주조</text>'
              '<text class="lbl" x="190" y="215">보조</text>'
              '<text class="lbl" x="320" y="215">강조</text>'
              '<text class="cap" x="60" y="320">제한된 팔레트(주조1·보조1·강조1)로 통일감.</text>')
    return _svg("color_harmony", '', cons, labels,
                "주조1 + 보조1 + 강조1로 팔레트를 좁혀.")


def linear_perspective():
    # 1점 투시: 눈높이(지평선) + 소실점 하나로 길·건물 가장자리가 수렴.
    vx, vy = 240, 205
    guide = f'<line class="guide" x1="40" y1="{vy}" x2="440" y2="{vy}"/>'
    cons = (
        f'<line class="cons" x1="120" y1="430" x2="{vx}" y2="{vy}"/>'      # 길 좌
        f'<line class="cons" x1="360" y1="430" x2="{vx}" y2="{vy}"/>'      # 길 우
        f'<line class="consd" x1="60" y1="110" x2="{vx}" y2="{vy}"/>'      # 건물 위 좌
        f'<line class="consd" x1="60" y1="330" x2="{vx}" y2="{vy}"/>'      # 건물 아래 좌
        f'<line class="consd" x1="420" y1="110" x2="{vx}" y2="{vy}"/>'     # 우
        f'<line class="consd" x1="420" y1="330" x2="{vx}" y2="{vy}"/>'
        f'<rect class="guide" x="60" y="110" width="90" height="220"/>'    # 좌 건물 면
        f'<rect class="guide" x="330" y="110" width="90" height="220"/>'   # 우 건물 면
        f'<circle class="dot" cx="{vx}" cy="{vy}" r="7"/>'
    )
    labels = (f'<text class="lbl" x="{vx+12}" y="{vy-8}">소실점</text>'
              f'<text class="lbl" x="44" y="{vy-8}">눈높이(지평선)</text>')
    return _svg("linear_perspective", guide, cons, labels,
                "눈높이 선과 소실점 하나로 가장자리들을 모아.")


def atmospheric_perspective():
    # 물러나는 능선: 멀수록 밝고(값↑) 대비·채도↓. 좌상에 근·중·원 명도 스와치.
    cons = (
        '<path d="M40 150 Q150 120 240 148 T440 144 L440 205 L40 205 Z" fill="#c4cad3"/>'  # 원경(밝음)
        '<path d="M40 215 Q160 175 280 210 T440 206 L440 285 L40 285 Z" fill="#8b94a3"/>'  # 중경
        '<path d="M40 305 Q150 258 260 302 T440 298 L440 430 L40 430 Z" fill="#3b424e"/>'  # 근경(어둠)
    )
    bars = ""
    for i, (c, t, ink) in enumerate([("#3b424e", "근", "#e9edf2"),
                                     ("#8b94a3", "중", INK), ("#c4cad3", "원", INK)]):
        x = 60 + i * 56
        bars += f'<rect x="{x}" y="60" width="44" height="44" rx="4" fill="{c}"/>'
        bars += f'<text class="tag" x="{x+22}" y="88" text-anchor="middle" fill="{ink}">{t}</text>'
    labels = '<text class="lbl" x="240" y="92">멀수록 대비↓ 채도↓ 밝기↑</text>'
    return _svg("atmospheric_perspective", "", cons + bars, labels,
                "원경의 대비·채도를 낮춰 공기와 거리감을.")


def depth_layering():
    # 근·중·원경 3층을 명도로 분리 + 근경 형태가 중경을 가리는 '겹침' 단서.
    cons = (
        '<rect x="40" y="70" width="400" height="95" fill="#cdd3dc"/>'      # 원경(밝음)
        f'<text class="tag" x="56" y="122" fill="{INK}">원경</text>'
        '<rect x="40" y="165" width="400" height="95" fill="#909aa8"/>'     # 중경
        f'<text class="tag" x="56" y="217" fill="{INK}">중경</text>'
        '<rect x="40" y="260" width="400" height="130" fill="#3f4651"/>'    # 근경(어둠)
        '<text class="tag" x="56" y="312" fill="#e9edf2">근경</text>'
        # 겹침: 근경 언덕이 중경 경계를 넘어 가림
        '<path class="cons" d="M250 260 q55 -70 120 -8 q14 50 -30 56 q-70 8 -90 -48 Z" '
        'fill="#3f4651"/>'
    )
    return _svg("depth_layering", "", cons, "",
                "근·중·원경을 명도로 나누고 겹침을 한 군데.")


def horizon_placement():
    # 3분할 격자 + 좋은 지평선(아래 1/3, 하늘 우세) vs 중앙(✗).
    fx, fy, fw, fh = 60, 60, 360, 360
    third = fy + fh * 2 / 3
    cons = (
        f'<rect class="gfill" x="{fx}" y="{fy}" width="{fw}" height="{fh*2/3:.0f}"/>'   # 하늘 영역
        f'<rect class="guide" x="{fx}" y="{fy}" width="{fw}" height="{fh}"/>'
        f'<line class="consd" x1="{fx}" y1="{fy+fh/3:.0f}" x2="{fx+fw}" y2="{fy+fh/3:.0f}"/>'
        f'<line class="consd" x1="{fx}" y1="{third:.0f}" x2="{fx+fw}" y2="{third:.0f}"/>'
        f'<line class="cons" x1="{fx}" y1="{third:.0f}" x2="{fx+fw}" y2="{third:.0f}"/>'  # 좋은 지평선
        f'<line class="acc" x1="{fx}" y1="{fy+fh/2:.0f}" x2="{fx+fw}" y2="{fy+fh/2:.0f}" '
        'stroke-dasharray="4 5"/>'                                                       # 중앙(나쁨)
    )
    labels = (f'<text class="lbl" x="{fx+8}" y="{third-10:.0f}">지평선 = 아래 1/3</text>'
              f'<text class="lbl" x="{fx+8}" y="{fy+26}">하늘이 주연</text>'
              f'<text class="tag" x="{fx+fw-66}" y="{fy+fh/2-8:.0f}" fill="{ACC}">중앙 ✗</text>')
    return _svg("horizon_placement", "", cons, labels,
                "지평선을 위/아래 1/3에 — 정중앙은 피해.")


DIAGRAMS = {
    "hand_structure": hand_structure, "proportion": proportion,
    "weight_balance": weight_balance, "foreshortening": foreshortening,
    "action_line": action_line, "joint_articulation": joint_articulation,
    "value_structure": value_structure, "light_direction": light_direction,
    "composition_balance": composition_balance, "color_harmony": color_harmony,
    "linear_perspective": linear_perspective,
    "atmospheric_perspective": atmospheric_perspective,
    "depth_layering": depth_layering, "horizon_placement": horizon_placement,
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "construction"
    os.makedirs(out, exist_ok=True)
    for name, fn in DIAGRAMS.items():
        path = os.path.join(out, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn())
        print("wrote", path)
    print(f"\n{len(DIAGRAMS)}개 구축 다이어그램 생성 완료 → {out}/")


if __name__ == "__main__":
    main()
