"""blender --background --python render_batch.py 로 실행 (Phase 5, 검증 통과 후).
MakeHuman export(CC0) → 포즈/앵글/조명 변형 그리드 → 렌더 → ingest(source_type=self_render).
포즈 데이터도 CC0/자체 소유만(AMASS 등 연구 모캡 금지)."""
import itertools

POSES = ["running", "standing", "reaching"]      # CC0/자체 포즈만
ANGLES = [("low", -20), ("eye", 0), ("high", 20)]
LIGHTS = ["side", "rim", "flat"]

def main():
    for pose, (aname, ax), light in itertools.product(POSES, ANGLES, LIGHTS):
        # 1) MakeHuman export 로드 + 포즈 적용  2) 카메라각 ax, 조명 light
        # 3) 렌더 → PNG  4) ingest(pil, source_type="self_render", license="CC0",
        #      personas=["pose","anatomy"], tags={"camera":aname,"lighting":light},
        #      render_params={"pose":pose,"camera":aname,"lighting":light})
        print("TODO render:", pose, aname, light)

if __name__ == "__main__":
    main()
