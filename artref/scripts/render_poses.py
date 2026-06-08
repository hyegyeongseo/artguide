"""
render_poses.py - Blender 헤드리스 배치 렌더러 (포즈 레퍼런스 라이브러리).

실행 (Blender 4.2+ 권장):
    blender -b -P render_poses.py

입력  : 애니메이션이 베이크된 FBX 클립 폴더(메시+리그+애니메이션 한 파일).
        예) MakeHuman(CC0) 캐릭터를 Mixamo에 올려 받은 동작별 FBX, 또는
        CC0로 리타게팅된 CMU-FBX 세트. FBX 1개 = 동작 1개.
출력  : <OUT_DIR>/<body>/<clip>/<pose_id>/<view>.png   (투명 RGBA PNG)
        <OUT_DIR>/manifest.jsonl                        (이미지 1장당 JSON 1줄)

.blend 불필요: 씬·조명·카메라를 스크립트가 직접 구성한다.
조명 에너지는 캐릭터 스케일에 맞춰 한 번 튜닝하고 그대로 두면 된다.

이번 확장:
  - CHARACTERS: 체형·성별 여러 베이스를 한 번에 순회(다양성).
  - 디테일 크롭: 손/발/머리를 본 기준으로 줌인해 별도 렌더("손이 어색해요" 대비).
  ※ 디테일 크롭의 카메라 프레이밍은 리그 본 이름에 의존 → Blender에서 첫 렌더로
    확인하고 DETAIL_* 상수를 조정할 것. 실패해도 전신 렌더는 그대로 나온다(방어적).
"""

import bpy
import os
import json
import math
import glob
import re
import datetime
from mathutils import Vector

# ============================ CONFIG (편집) ============================
# 체형·성별 다양성: 각 캐릭터의 '애니메이션 FBX 폴더'를 하나의 엔트리로.
# 같은 동작 세트를 체형별로 따로 받아(각 MakeHuman 캐릭터를 Mixamo에 올려) 폴더를 나눈다.
CHARACTERS = [
    # {"clips_dir": "/path/to/fbx/female_avg",   "body_type": "female_avg",   "gender": "female"},
    # {"clips_dir": "/path/to/fbx/male_muscular", "body_type": "male_muscular", "gender": "male"},
    {"clips_dir": "/path/to/animated_fbx", "body_type": "default", "gender": "unspecified"},
]
OUT_DIR = "/path/to/output"               # 렌더 + manifest 출력 위치

FRAME_STEP         = 12                    # 클립당 N프레임마다 포즈 1개 샘플
MAX_POSES_PER_CLIP = 8                     # 클립당 포즈 상한 (None=무제한)
VIEW_ANGLES        = [0, 45, 90, 135, 180, 225, 270, 315]  # 전신 azimuth(도)
ELEVATIONS         = [12]                  # 카메라 고도(도). 예: [12, 35]

RES        = 1024                          # 정사각 렌더 해상도(px)
SAMPLES    = 16                            # EEVEE 샘플
CAM_MARGIN = 1.30                          # 프레이밍 여백(1.0=타이트)

CLAY       = True                          # 모든 재질을 무광 클레이로 덮기(형태 읽힘↑)
CLAY_COLOR = (0.72, 0.70, 0.67)            # 중립 클레이 톤

SKIP_EXISTING = True                       # 이미 있는 파일 재렌더 안 함(중단·재개)

# --- 디테일 크롭 (손/발/머리) ---
DETAIL_CROPS       = True
DETAIL_VIEW_ANGLES = [0, 135]              # 크롭은 각도 적게(정면·3/4 뒤)
DETAIL_PAD         = 1.8                   # 크롭 프레이밍 여백(작은 부위라 여유)
# region -> 본 이름에 포함될 패턴(소문자, 리그마다 다름 → 필요시 보강)
DETAIL_REGIONS = {
    "hand": ["hand"],
    "foot": ["foot", "toe", "ball"],
    "head": ["head"],
}

# 조명 에너지(Area 라이트, W). 스케일에 맞춰 한 번만 튜닝.
KEY_ENERGY, FILL_ENERGY, RIM_ENERGY = 800.0, 250.0, 400.0
WORLD_STRENGTH = 0.35

# 클립명 키워드 -> 거친 카테고리. 자유 확장.
CATEGORY_MAP = {
    "run": "locomotion", "walk": "locomotion", "jump": "locomotion", "sprint": "locomotion",
    "sit": "rest", "idle": "rest", "stand": "rest", "lean": "rest", "lie": "rest",
    "kick": "action", "punch": "action", "sword": "action", "throw": "action", "fight": "action",
    "dance": "expressive", "spin": "expressive", "wave": "expressive",
}
# =========================================================================


def log(msg):
    print(f"[render_poses] {msg}", flush=True)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.armatures, bpy.data.lights, bpy.data.cameras):
        for b in list(block):
            if b.users == 0:
                block.remove(b)


def setup_render():
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    try:
        scene.eevee.taa_render_samples = SAMPLES
    except AttributeError:
        pass
    scene.render.film_transparent = True
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    world = bpy.data.worlds.new("ref_world")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1.0)
        bg.inputs[1].default_value = WORLD_STRENGTH
    scene.world = world


def make_area_light(name, energy, size=3.0):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return obj


def setup_camera_and_lights():
    cam_data = bpy.data.cameras.new("ref_cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("ref_cam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    target = bpy.data.objects.new("ref_target", None)
    bpy.context.collection.objects.link(target)

    trk = cam.constraints.new(type="TRACK_TO")
    trk.target = target
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"

    key = make_area_light("key", KEY_ENERGY, size=4.0)
    fill = make_area_light("fill", FILL_ENERGY, size=6.0)
    rim = make_area_light("rim", RIM_ENERGY, size=3.0)
    return cam, target, (key, fill, rim)


def _rot_xy(x, y, az):
    c, s = math.cos(az), math.sin(az)
    return x * c - y * s, x * s + y * c


def place_rig(cam, target, lights, center, radius, az_deg, el_deg):
    """카메라+3조명을 구면에 배치. 조명은 azimuth를 따라 돌아 모든 뷰가 일관."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    target.location = center
    cx = math.sin(az) * math.cos(el)
    cy = -math.cos(az) * math.cos(el)
    cz = math.sin(el)
    cam.location = center + Vector((cx, cy, cz)) * radius

    offsets = [(-0.7, -1.0, 1.1), (0.9, -0.8, 0.3), (0.2, 1.0, 0.9)]  # key, fill, rim
    for lt, (ox, oy, oz) in zip(lights, offsets):
        rx, ry = _rot_xy(ox, oy, az)
        lt.location = center + Vector((rx, ry, oz)) * radius * 1.6
        d = (center - lt.location)
        lt.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def import_fbx(path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.context.scene.objects if o not in before]
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    meshes = [o for o in new if o.type == "MESH"]
    return arm, meshes, new


def _pts_extents(pts):
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (mn + mx) / 2.0, (mx - mn)


def posed_extents(armature):
    mw = armature.matrix_world
    pts = []
    for pb in armature.pose.bones:
        pts.append(mw @ pb.head)
        pts.append(mw @ pb.tail)
    if not pts:
        return Vector((0, 0, 1)), Vector((1, 1, 2))
    return _pts_extents(pts)


def _side_of(name):
    n = name.lower()
    if "left" in n or n.endswith(".l") or n.endswith("_l") or n.startswith("l_"):
        return "left"
    if "right" in n or n.endswith(".r") or n.endswith("_r") or n.startswith("r_"):
        return "right"
    return "center"


def detail_groups(armature, patterns):
    """region 패턴에 맞는 본을 side(left/right/center)별로 묶어 (side, [bones]) 반환."""
    matched = [pb for pb in armature.pose.bones
               if any(p in pb.name.lower() for p in patterns)]
    groups = {}
    for pb in matched:
        groups.setdefault(_side_of(pb.name), []).append(pb)
    return [(side, bones) for side, bones in groups.items() if bones]


def region_extents(armature, bones):
    """선택 본들(+자식 tail까지)의 중심·크기 → 손가락/발가락까지 프레이밍."""
    mw = armature.matrix_world
    pts = []
    for pb in bones:
        pts.append(mw @ pb.head)
        pts.append(mw @ pb.tail)
        for ch in pb.children:
            pts.append(mw @ ch.tail)
    if not pts:
        return None, None
    return _pts_extents(pts)


def apply_clay(meshes):
    mat = bpy.data.materials.new("clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*CLAY_COLOR, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85
    for m in meshes:
        m.data.materials.clear()
        m.data.materials.append(mat)


def tags_from_name(clip):
    tokens = [t.lower() for t in re.split(r"[^A-Za-z]+", clip) if len(t) > 1]
    category = "other"
    for kw, cat in CATEGORY_MAP.items():
        if any(kw in t for t in tokens):
            category = cat
            break
    return category, tokens


def remove_objects(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        if o.name in bpy.context.scene.objects:
            o.select_set(True)
    bpy.ops.object.delete()


def render_view(out_png):
    bpy.context.scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)


def radius_for(cam, size, margin):
    fit = max(size.x, size.y, size.z, 0.15)
    return (fit * margin / 2.0) / math.tan(cam.data.angle / 2.0)


def write_manifest(mf, *, rid, pose_id, clip, frame, az, el, category, tags,
                   body_type, gender, region, rel):
    mf.write(json.dumps({
        "id": rid, "pose_id": pose_id, "clip": clip, "frame": frame,
        "azimuth": az, "elevation": el, "category": category, "tags": tags,
        "body_type": body_type, "gender": gender, "region": region,
        "material": "clay" if CLAY else "textured",
        "width": RES, "height": RES, "path": rel,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }, ensure_ascii=False) + "\n")
    mf.flush()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = open(os.path.join(OUT_DIR, "manifest.jsonl"), "a", encoding="utf-8")

    clear_scene()
    setup_render()
    cam, target, lights = setup_camera_and_lights()

    for char in CHARACTERS:
        cdir, body_type, gender = char["clips_dir"], char["body_type"], char["gender"]
        clips = sorted(glob.glob(os.path.join(cdir, "*.fbx")))
        log(f"character '{body_type}'({gender}) — {len(clips)} clip(s) in {cdir}")

        for ci, path in enumerate(clips, 1):
            clip = os.path.splitext(os.path.basename(path))[0]
            log(f"  [{ci}/{len(clips)}] {clip}")
            arm, meshes, new_objs = import_fbx(path)
            if arm is None or not meshes:
                log(f"    skip (no armature/mesh): {clip}")
                remove_objects(new_objs)
                continue
            if CLAY:
                apply_clay(meshes)

            category, tokens = tags_from_name(clip)
            scene = bpy.context.scene
            frames = list(range(scene.frame_start, scene.frame_end + 1, FRAME_STEP)) \
                or [scene.frame_start]
            if MAX_POSES_PER_CLIP:
                frames = frames[:MAX_POSES_PER_CLIP]

            for f in frames:
                scene.frame_set(f)
                bpy.context.view_layer.update()
                center, size = posed_extents(arm)
                radius = radius_for(cam, size, CAM_MARGIN)
                pose_id = f"{body_type}_{clip}_{f:04d}"
                pose_dir = os.path.join(OUT_DIR, body_type, clip, pose_id)
                os.makedirs(pose_dir, exist_ok=True)

                # --- 전신 턴테이블 ---
                for el in ELEVATIONS:
                    for az in VIEW_ANGLES:
                        view = f"az{az:03d}_el{el:02d}"
                        out_png = os.path.join(pose_dir, view + ".png")
                        rel = os.path.relpath(out_png, OUT_DIR)
                        if not (SKIP_EXISTING and os.path.exists(out_png)):
                            place_rig(cam, target, lights, center, radius, az, el)
                            render_view(out_png)
                        write_manifest(manifest, rid=f"{pose_id}_{view}", pose_id=pose_id,
                                       clip=clip, frame=f, az=az, el=el, category=category,
                                       tags=tokens, body_type=body_type, gender=gender,
                                       region="full", rel=rel)

                # --- 디테일 크롭 (손/발/머리) ---  ※ Blender에서 프레이밍 확인·조정
                if DETAIL_CROPS:
                    try:
                        for region, patterns in DETAIL_REGIONS.items():
                            for side, bones in detail_groups(arm, patterns):
                                rc, rsize = region_extents(arm, bones)
                                if rc is None:
                                    continue
                                rrad = radius_for(cam, rsize, DETAIL_PAD)
                                for az in DETAIL_VIEW_ANGLES:
                                    el = ELEVATIONS[0]
                                    view = f"{region}_{side}_az{az:03d}"
                                    out_png = os.path.join(pose_dir, view + ".png")
                                    rel = os.path.relpath(out_png, OUT_DIR)
                                    if not (SKIP_EXISTING and os.path.exists(out_png)):
                                        place_rig(cam, target, lights, rc, rrad, az, el)
                                        render_view(out_png)
                                    # 크롭은 region을 태그에 넣어 적재 시 persona(hand 등) 매핑되게
                                    write_manifest(manifest, rid=f"{pose_id}_{view}",
                                                   pose_id=pose_id, clip=clip, frame=f, az=az,
                                                   el=el, category=category,
                                                   tags=tokens + [region, side],
                                                   body_type=body_type, gender=gender,
                                                   region=region, rel=rel)
                    except Exception as e:
                        log(f"    detail-crop 건너뜀({pose_id}): {type(e).__name__}: {e}")

            remove_objects(new_objs)

    manifest.close()
    log("done.")


if __name__ == "__main__":
    main()
