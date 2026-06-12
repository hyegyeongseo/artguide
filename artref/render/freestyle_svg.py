"""freestyle_svg.py — Blender 헤드리스에서 구축선(라인) SVG 추출 (Phase 4).

⚠️ 이 코드는 당신의 Blender(헤드리스)에서 실행됩니다. 컨테이너 Python이 아니라
   render_poses.py 와 같은 Blender 세션 안에서 import/호출하세요.

같은 3D 씬에 '패스 하나'를 더 얹는 일 — 사실적 윤곽선(실루엣+크리스)을 SVG로 뽑습니다.
render_poses 의 뷰 렌더 직후, 같은 프레임/카메라에서 호출하면 PNG 옆에 .svg 가 남습니다.

라인셋을 silhouette / crease 로 나눠 export 후, <g id="contour"> / <g id="construction">
로 감싸 프론트에서 토글 가능하게 후처리합니다(Freestyle SVG Exporter의 그룹 분리 한계를
색/레이어 기준 단순 후처리로 보완).

설정(한 번):
  1) Blender에 'Freestyle SVG Export' 애드온 활성화 (아래 enable_svg_addon()).
  2) 씬에서 Freestyle 사용 on (render.use_freestyle = True).

통합 예 (render_poses.py 의 뷰 루프 안):
  from freestyle_svg import enable_svg_addon, setup_lineart, export_svg_for_frame
  enable_svg_addon(); setup_lineart()           # 시작 시 1회
  ...
  bpy.context.scene.frame_set(f)
  # (카메라/뷰 세팅 후)
  export_svg_for_frame(out_svg_path)            # PNG 렌더와 같은 지점에서
"""
import bpy
import os
import re


def enable_svg_addon():
    """Freestyle SVG Exporter 애드온 활성화(헤드리스에선 명시적으로 켜야 함)."""
    try:
        bpy.ops.preferences.addon_enable(module="render_freestyle_svg")
    except Exception as e:
        print(f"[freestyle] addon_enable 실패(이미 켜졌을 수 있음): {e}")


def setup_lineart(scene=None):
    """Freestyle on + 라인셋 2개(silhouette / crease) 구성."""
    scene = scene or bpy.context.scene
    scene.render.use_freestyle = True
    # SVG export 설정(애드온이 제공하는 svg 속성)
    svg = getattr(scene, "svg_export", None)
    if svg is not None:
        svg.use_svg_export = True
        svg.mode = "FRAME"            # 프레임 단위 출력
        svg.line_join_type = "ROUND"

    view_layer = scene.view_layers[0]
    fs = view_layer.freestyle_settings
    # 기존 라인셋 정리
    while fs.linesets:
        fs.linesets.remove(fs.linesets[0])

    # ① 외곽선(실루엣) → contour 레이어
    ls1 = fs.linesets.new("silhouette")
    ls1.select_silhouette = True
    ls1.select_border = True
    ls1.select_crease = False
    ls1.linestyle.color = (0.10, 0.11, 0.13)   # 잉크색
    ls1.linestyle.thickness = 2.2

    # ② 크리스(접힘/구조선) → construction 레이어
    ls2 = fs.linesets.new("crease")
    ls2.select_silhouette = False
    ls2.select_border = False
    ls2.select_crease = True
    ls2.linestyle.color = (0.88, 0.33, 0.24)   # 구축선 빨강
    ls2.linestyle.thickness = 1.6


def export_svg_for_frame(out_svg_path):
    """현재 프레임을 렌더하면서 SVG를 떨군 뒤, 그룹 후처리해 out_svg_path 로 저장.

    Freestyle SVG Exporter는 렌더 시점에 <scene.svg_export> 경로로 .svg 를 쓴다.
    여기서는 임시 출력 후 그룹을 입혀 최종 경로로 옮긴다.
    """
    scene = bpy.context.scene
    # 애드온은 보통 렌더 출력 경로 기준으로 svg 를 쓴다. 안전하게 임시 파일명을 맞춘다.
    tmp = out_svg_path + ".raw.svg"
    scene.render.filepath = os.path.splitext(tmp)[0]
    bpy.ops.render.render(write_still=True)     # 이 호출이 svg도 함께 생성
    # 애드온 산출 svg 후보 경로(버전별 차이 대비)
    cand = [tmp, os.path.splitext(tmp)[0] + ".svg",
            os.path.splitext(tmp)[0] + f"{scene.frame_current:04d}.svg"]
    src = next((p for p in cand if os.path.exists(p)), None)
    if not src:
        print(f"[freestyle] svg 산출 못 찾음: {cand}")
        return None
    _group_layers(src, out_svg_path)
    try:
        os.remove(src)
    except OSError:
        pass
    return out_svg_path


def _group_layers(src, dst):
    """색 기준으로 path 들을 <g id="contour"> / <g id="construction"> 로 감싼다.

    silhouette(잉크색)·crease(빨강)를 stroke 색으로 구분해 두 그룹으로 분리.
    프론트에서 그룹 토글(구축선만/외곽만)이 가능해진다.
    """
    svg = open(src, encoding="utf-8").read()
    contour, construction = [], []
    for m in re.finditer(r"<(path|polyline|line)[^>]*?/>", svg):
        el = m.group(0)
        # 빨강 계열(crease) vs 그 외(contour) 단순 분류
        if re.search(r"stroke\s*:\s*#?(e0|df|e1|cc5|d1|rgb\(2\d\d)", el, re.I) \
           or "0.88" in el or "224" in el:
            construction.append(el)
        else:
            contour.append(el)
    head = re.match(r"<svg[^>]*>", svg)
    head = head.group(0) if head else '<svg xmlns="http://www.w3.org/2000/svg">'
    out = (head
           + '\n<g id="contour">\n' + "\n".join(contour) + "\n</g>"
           + '\n<g id="construction">\n' + "\n".join(construction) + "\n</g>"
           + "\n</svg>\n")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(out)


# 적재 측 연결(참고):
#   export 한 .svg 바이트를 render 메타와 함께 ingest(..., svg_bytes=open(svg,'rb').read()) 로 넘기면
#   ingest.py 가 svg/{ref_id}.svg 로 저장하고 svg_key 를 채운다. /svg/{ref_id} 로 서빙.
