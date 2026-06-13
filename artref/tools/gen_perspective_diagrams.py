"""gen_perspective_diagrams.py — 원근·깊이 4축의 교육 도식 보강 세트.

빈 축을 채운다: linear_perspective · atmospheric_perspective · depth_layering · horizon_placement.
(다른 10축은 reference/에 5~10개씩 있는데 이 4축만 construction 도식 1장뿐, reference 교육 도식 0이었음.)

`gen_reference_diagrams.py`와 *완전히 같은 시각 계약*을 재사용한다(_svg/색토큰/3레이어/한글 캡션).
★ 비파괴: 기존 reference/*.svg 60개와 manifest는 그대로 두고, 새 SVG만 쓰고 manifest를 **병합**한다.
   추가로 기존 원근 SVG(one_point_perspective 등)를 이 4축으로 **재매핑**한다(지금은 foreshortening에만 걸려 있음).

실행:  python tools/gen_perspective_diagrams.py [out_dir]   (기본 ../woz/public/reference)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_reference_diagrams import _svg, GUIDE, CONS, ACC, INK  # 동일 계약 재사용

# 명도 회색(공기원근/깊이용 — 멀수록 옅게)
V1, V2, V3, V4 = "#3f444c", "#70757f", "#a1a6ae", "#cdd1d6"


def two_point_perspective():
    # 지평선 y=200, 좌우 소실점, 가운데 수직 앞모서리에서 양옆으로 수렴하는 상자.
    A, B = (240, 150), (240, 295)          # 앞 수직모서리(위/아래)
    C, D = (160, 170), (160, 257)          # 왼면 수직모서리
    E, F = (320, 170), (320, 257)          # 오른면 수직모서리
    guide = '<line class="guide" x1="20" y1="200" x2="460" y2="200"/>'
    cons = (
        # 소실점으로 가는 구축선(점선)
        f'<line class="consd" x1="{A[0]}" y1="{A[1]}" x2="40" y2="200"/>'
        f'<line class="consd" x1="{B[0]}" y1="{B[1]}" x2="40" y2="200"/>'
        f'<line class="consd" x1="{A[0]}" y1="{A[1]}" x2="440" y2="200"/>'
        f'<line class="consd" x1="{B[0]}" y1="{B[1]}" x2="440" y2="200"/>'
        # 상자 실선 모서리
        f'<line class="cons" x1="{A[0]}" y1="{A[1]}" x2="{B[0]}" y2="{B[1]}"/>'
        f'<line class="cons" x1="{C[0]}" y1="{C[1]}" x2="{D[0]}" y2="{D[1]}"/>'
        f'<line class="cons" x1="{E[0]}" y1="{E[1]}" x2="{F[0]}" y2="{F[1]}"/>'
        f'<line class="cons" x1="{A[0]}" y1="{A[1]}" x2="{C[0]}" y2="{C[1]}"/>'
        f'<line class="cons" x1="{B[0]}" y1="{B[1]}" x2="{D[0]}" y2="{D[1]}"/>'
        f'<line class="cons" x1="{A[0]}" y1="{A[1]}" x2="{E[0]}" y2="{E[1]}"/>'
        f'<line class="cons" x1="{B[0]}" y1="{B[1]}" x2="{F[0]}" y2="{F[1]}"/>'
        '<circle class="adot" cx="40" cy="200" r="5"/>'
        '<circle class="adot" cx="440" cy="200" r="5"/>')
    labels = ('<text class="lbl" x="24" y="190">VP</text>'
              '<text class="lbl" x="420" y="190">VP</text>'
              '<text class="lbl" x="300" y="196" fill="' + INK + '">지평선(눈높이)</text>')
    return _svg("two_point_perspective", guide, cons, labels,
                "소실점 2개 — 앞 수직모서리에서 양옆 VP로 모서리가 수렴한다.")


def vanishing_point_convergence():
    # 한 소실점으로 모이는 길 + 같은 간격 기둥이 멀수록 좁아짐.
    vp = (240, 170)
    guide = ('<line class="guide" x1="20" y1="170" x2="460" y2="170"/>'
             f'<path class="gfill" d="M90 440 L{vp[0]} {vp[1]} L390 440 Z"/>')
    posts = ""
    # 길 왼쪽 가장자리 위 기둥: x가 vp로 갈수록 짧아짐
    for x, yb, h in [(112, 430, 95), (165, 320, 55), (203, 250, 32), (224, 212, 18)]:
        posts += f'<line class="cons" x1="{x}" y1="{yb}" x2="{x}" y2="{yb-h}"/>'
    cons = (f'<line class="cons" x1="90" y1="440" x2="{vp[0]}" y2="{vp[1]}"/>'
            f'<line class="cons" x1="390" y1="440" x2="{vp[0]}" y2="{vp[1]}"/>'
            f'<line class="consd" x1="112" y1="335" x2="224" y2="194"/>'  # 기둥 윗끝 수렴 보조선
            + posts +
            f'<circle class="adot" cx="{vp[0]}" cy="{vp[1]}" r="5"/>')
    labels = ('<text class="lbl" x="250" y="166">소실점</text>'
              '<text class="lbl" x="60" y="430" fill="' + INK + '">평행선 → 한 점</text>'
              '<text class="lbl" x="250" y="300" fill="' + INK + '">같은 간격도 멀수록 좁게</text>')
    return _svg("vanishing_point_convergence", guide, cons, labels,
                "평행선은 소실점 하나로 모이고, 같은 크기·간격도 멀수록 작아진다.")


def atmospheric_recession():
    # 4겹 능선: 앞(진하고 또렷) → 뒤(옅고 흐림). 멀수록 명도↑·대비↓·차갑게.
    bands = (
        f'<path d="M0 175 Q120 150 240 168 T480 162 V210 H0 Z" fill="{V4}"/>'
        f'<path d="M0 215 Q140 188 280 208 T480 205 V255 H0 Z" fill="{V3}"/>'
        f'<path d="M0 258 Q120 228 250 252 T480 246 V305 H0 Z" fill="{V2}"/>'
        f'<path d="M0 305 Q150 270 300 300 T480 292 V440 H0 Z" fill="{V1}"/>')
    guide = bands
    cons = ('<line class="accd" x1="440" y1="300" x2="440" y2="170"/>'
            '<path class="acc" d="M440 178 l-6 12 h12 z" fill="' + ACC + '"/>')
    labels = ('<text class="lbl" x="20" y="335" fill="#f0f0f0">가까움 — 진하고 또렷</text>'
              '<text class="lbl" x="250" y="160" fill="' + INK + '">멀어짐 — 옅고·대비↓·차갑게</text>')
    return _svg("atmospheric_recession", guide, cons, labels,
                "멀어질수록 명도는 올라가고 대비는 줄며 색이 차가워진다(공기원근).")


def edge_detail_falloff():
    # 가까운 나무: 또렷한 가장자리+디테일 / 먼 나무: 흐릿(blur)·단순.
    defs = ('<defs><filter id="far" x="-20%" y="-20%" width="140%" height="140%">'
            '<feGaussianBlur stdDeviation="3.2"/></filter></defs>')
    near = (f'<path d="M150 300 L110 300 L150 150 L190 300 Z" fill="{V1}"/>'
            f'<rect x="144" y="300" width="12" height="40" fill="{V1}"/>'
            f'<path class="cons" d="M150 200 l-22 26 M150 235 l24 28 M150 175 l16 20"/>')  # 디테일
    far = (f'<g filter="url(#far)">'
           f'<path d="M330 300 L302 300 L330 195 L358 300 Z" fill="{V3}"/>'
           f'<rect x="325" y="300" width="9" height="28" fill="{V3}"/></g>')
    guide = '<line class="guide" x1="20" y1="340" x2="460" y2="340"/>'
    cons = near + far
    labels = ('<text class="lbl" x="96" y="368" fill="' + INK + '">또렷한 가장자리 · 디테일</text>'
              '<text class="lbl" x="290" y="368" fill="' + INK + '">흐릿 · 단순</text>')
    return _svg("edge_detail_falloff", guide, cons, labels,
                "가까운 가장자리는 또렷·디테일, 먼 것은 흐릿·단순해진다.", defs=defs)


def depth_planes():
    # 전경(큼·진함) / 중경 / 원경(작음·옅음) 겹침.
    bg = f'<path d="M120 200 L200 130 L270 185 L340 120 L430 200 V230 H120 Z" fill="{V3}"/>'
    mg = f'<path d="M40 280 Q170 220 320 270 T470 268 V330 H40 Z" fill="{V2}"/>'
    fg = (f'<path d="M60 440 Q90 300 150 300 Q210 300 230 440 Z" fill="{V1}"/>'
          f'<rect x="300" y="330" width="120" height="110" rx="8" fill="{V1}"/>')
    guide = bg + mg
    cons = fg
    labels = ('<text class="lbl" x="320" y="150" fill="' + INK + '">원경 (작고 옅게)</text>'
              '<text class="lbl" x="60" y="300" fill="' + INK + '">중경</text>'
              '<text class="lbl" x="70" y="420" fill="#f0f0f0">전경 (크고 진하게)</text>')
    return _svg("depth_planes", guide, cons, labels,
                "전경·중경·원경 — 겹침 + 크기 + 명도차가 함께 깊이를 만든다.")


def horizon_high_low():
    # 같은 요소, 지평선만 높/낮 → 땅 강조 vs 하늘 강조.
    def scene(ox, hy, label):
        sky = f'<rect x="{ox}" y="90" width="180" height="{hy-90}" fill="{V4}"/>'
        gnd = f'<rect x="{ox}" y="{hy}" width="180" height="{390-hy}" fill="{V2}"/>'
        line = f'<line class="cons" x1="{ox}" y1="{hy}" x2="{ox+180}" y2="{hy}"/>'
        tree = (f'<path d="M{ox+90} {hy-44} l-16 30 h32 z" fill="{V1}"/>'
                f'<rect x="{ox+86}" y="{hy-14}" width="8" height="14" fill="{V1}"/>')
        frame = f'<rect class="guide" x="{ox}" y="90" width="180" height="300"/>'
        lab = f'<text class="lbl" x="{ox+10}" y="84" fill="{INK}">{label}</text>'
        return sky + gnd + line + tree + frame + lab
    guide = ('<rect class="guide" x="40" y="90" width="180" height="300"/>'
             '<rect class="guide" x="260" y="90" width="180" height="300"/>')
    cons = scene(40, 150, "높은 지평선 → 땅 강조") + scene(260, 330, "낮은 지평선 → 하늘 강조")
    return _svg("horizon_high_low", guide, cons, "",
                "지평선 높낮이를 바꾸면 같은 장면도 땅(전경) 또는 하늘이 주인공이 된다.")


def eye_level_horizon():
    # 눈높이선 기준 위 상자=밑면 보임 / 아래 상자=윗면 보임.
    hy = 240
    guide = f'<line class="guide" x1="20" y1="{hy}" x2="460" y2="{hy}"/>'
    # 위 상자(밑면 보임)
    up = ('<rect class="cons" x="110" y="150" width="80" height="56"/>'
          f'<path class="cons" d="M110 206 L190 206 L208 192 L128 192 Z" fill="{V3}"/>')
    # 아래 상자(윗면 보임)
    dn = ('<rect class="cons" x="290" y="278" width="80" height="56"/>'
          f'<path class="cons" d="M290 278 L370 278 L388 264 L308 264 Z" fill="{V3}"/>')
    cons = up + dn
    labels = ('<text class="lbl" x="300" y="232" fill="' + INK + '">눈높이</text>'
              '<text class="lbl" x="96" y="142" fill="' + INK + '">위 → 밑면 보임</text>'
              '<text class="lbl" x="286" y="352" fill="' + INK + '">아래 → 윗면 보임</text>')
    return _svg("eye_level_horizon", guide, cons, labels,
                "눈높이보다 위면 밑면이, 아래면 윗면이 보인다 — 물체 위치로 시점을 읽는다.")


DIAGRAMS = {
    "two_point_perspective": two_point_perspective,
    "vanishing_point_convergence": vanishing_point_convergence,
    "atmospheric_recession": atmospheric_recession,
    "edge_detail_falloff": edge_detail_falloff,
    "depth_planes": depth_planes,
    "horizon_high_low": horizon_high_low,
    "eye_level_horizon": eye_level_horizon,
}

# 새 도식의 축/페르소나/캡션
MANIFEST = {
    "two_point_perspective": {"supports": ["linear_perspective"], "personas": ["perspective", "composition"],
                              "caption": "소실점 2개 — 양옆으로 수렴."},
    "vanishing_point_convergence": {"supports": ["linear_perspective"], "personas": ["perspective", "composition"],
                                    "caption": "평행선은 소실점으로, 같은 크기도 멀수록 작게."},
    "atmospheric_recession": {"supports": ["atmospheric_perspective"], "personas": ["perspective", "light"],
                              "caption": "멀수록 옅고·대비↓·차갑게."},
    "edge_detail_falloff": {"supports": ["atmospheric_perspective"], "personas": ["perspective", "light"],
                            "caption": "가까운 가장자리 또렷, 먼 것은 흐릿·단순."},
    "depth_planes": {"supports": ["depth_layering"], "personas": ["composition", "perspective"],
                     "caption": "전경·중경·원경 — 겹침+크기+명도로 깊이."},
    "horizon_high_low": {"supports": ["horizon_placement"], "personas": ["composition"],
                         "caption": "지평선 높낮이로 땅/하늘 강조 전환."},
    "eye_level_horizon": {"supports": ["horizon_placement", "linear_perspective"], "personas": ["composition", "perspective"],
                          "caption": "눈높이 위는 밑면, 아래는 윗면이 보인다."},
}

# 기존 원근 SVG 재매핑(현재 foreshortening에만 걸림 → 해당 축 추가)
REMAP = {
    "one_point_perspective": ["linear_perspective"],
    "perspective_grid": ["linear_perspective"],
    "ellipse_perspective": ["linear_perspective"],
    "overlapping_forms": ["depth_layering"],
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "..", "woz", "public", "reference")
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    # 1) 새 SVG만 기록(기존 파일 비파괴)
    for name, fn in DIAGRAMS.items():
        p = os.path.join(out, f"{name}.svg")
        with open(p, "w", encoding="utf-8") as f:
            f.write(fn())
        print("wrote", p)
    # 2) 기존 manifest 로드 후 병합(+재매핑)
    mpath = os.path.join(out, "manifest.json")
    data = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {"diagrams": {}}
    diags = data.get("diagrams", {})
    diags.update(MANIFEST)                                  # 새 항목 추가
    for name, add in REMAP.items():                         # 기존 항목 supports 보강
        if name in diags:
            sup = diags[name].setdefault("supports", [])
            for ax in add:
                if ax not in sup:
                    sup.append(ax)
    # 3) asset_index 재구성(병합된 diagrams 전체에서)
    index = {}
    for name, meta in diags.items():
        for sp in meta.get("supports", []):
            index.setdefault(sp, []).append({
                "type": "svg", "ref_id": f"reference/{name}.svg",
                "label": "도식", "caption": meta.get("caption", ""), "personas": meta.get("personas", []),
            })
    data["diagrams"] = diags
    data["asset_index"] = index
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("merged manifest →", mpath, f"(diagrams={len(diags)})")


if __name__ == "__main__":
    main()
