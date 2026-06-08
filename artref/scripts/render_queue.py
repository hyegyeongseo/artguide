"""미해결 miss_log → 렌더 보강 큐.

검색이 실패(빈 결과/낮은 점수)한 reference_query를 빈도순으로 모아,
render_poses 배치가 "무엇을 더 렌더해야 하는지" 알 수 있는 계획(JSON)으로 만든다.
이것이 'miss → render → ingest' 루프의 공급 절반을 반자동으로 닫는 연결고리다.

흐름:
    /guide 검색 실패 → mapping.log_miss → miss_log(count↑)
        → (이 스크립트) render_queue.json
        → 운영자/배치가 render_poses로 채움 → ingest(source_type=self_render)
        → 해당 term을 resolved 처리(--resolve)

sub_problem → 렌더 힌트(어떤 각도/크롭이 이 miss를 메우나)는 휴리스틱이며
render_poses의 상수와 맞춰 필요시 보강한다.

실행:
    cd artref
    docker compose exec -w /repo api python scripts/render_queue.py          # 큐 생성
    docker compose exec -w /repo api python scripts/render_queue.py --resolve "<term>"  # 채운 뒤 해제
"""
import json
import os
import sys

sys.path.insert(0, "api")
from sqlalchemy import text
from stores.db import engine

# sub_problem → render_poses에 줄 힌트(어떤 각도/크롭/조명이 이 miss를 메우나)
SP_RENDER_HINT = {
    "hand_structure":     {"detail_crop": "hand", "views": [0, 135],
                           "note": "손 평면이 읽히는 정면·3/4 크롭"},
    "foreshortening":     {"views": [0, 30, 60], "elevations": [12, 35],
                           "note": "팔/다리가 카메라로 뻗는 단축 각도"},
    "weight_balance":     {"views": [0, 90, 270], "note": "한 발 체중 이동 포즈"},
    "joint_articulation": {"views": [45, 135], "note": "굽은 관절을 보이는 포즈"},
    "action_line":        {"note": "동세 큰 포즈 클립 우선"},
    "proportion":         {"views": [0], "note": "전신 정면 비율 기준컷"},
    "value_structure":    {"lighting": ["side", "rim"], "note": "명암 폭 큰 조명"},
    "composition_balance": {"note": "미술관 CC0 구도 시드로 보강 가능"},
    "color_harmony":      {"note": "미술관 CC0 회화 시드로 보강 가능"},
    "light_direction":    {"lighting": ["side", "rim"], "note": "단일 광원 형태 스터디"},
}


def build_queue(limit=50):
    rows = []
    with engine.begin() as cx:
        for term, ctx, cnt in cx.execute(text(
                "SELECT term, context, count FROM miss_log "
                "WHERE resolved = 0 ORDER BY count DESC, id DESC LIMIT :n"), {"n": limit}):
            try:
                ctx = json.loads(ctx) if ctx else {}
            except Exception:
                ctx = {}
            sp = ctx.get("sub_problem")
            rows.append({
                "term": term,
                "count": int(cnt or 1),
                "sub_problem": sp,
                "persona": ctx.get("persona"),
                "measured": ctx.get("measured"),
                "top_score": ctx.get("top_score"),
                "render_hint": SP_RENDER_HINT.get(sp, {}),
            })
    # 측정된(measured) miss를 동순위에서 앞으로 — 근거 있는 수요가 더 가치 있는 보강 대상.
    rows.sort(key=lambda r: (-(r["count"]), not bool(r["measured"])))
    return rows


def resolve_term(term):
    with engine.begin() as cx:
        n = cx.execute(text("UPDATE miss_log SET resolved = 1 WHERE term = :t AND resolved = 0"),
                       {"t": term}).rowcount
    print(f"resolved {n} row(s) for term: {term}")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--resolve":
        resolve_term(sys.argv[2])
        return
    q = build_queue()
    # /repo는 읽기전용(:ro) 마운트라 CWD엔 못 쓴다 → 쓰기 가능한 기본 경로(/tmp).
    # RENDER_QUEUE_OUT 로 원하는 경로 지정 가능. 호스트로 빼려면 docker compose cp.
    out = os.environ.get("RENDER_QUEUE_OUT", "/tmp/render_queue.json")
    wrote = None
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        wrote = out
    except OSError as e:
        print(f"[render_queue] 파일 쓰기 실패({e.strerror}: {out}) → 콘솔 요약만 출력. "
              f"RENDER_QUEUE_OUT로 쓰기 가능 경로를 지정하세요.")
    print(f"미해결 miss {len(q)}건" + (f" → {wrote}" if wrote else "") + "\n")
    for r in q[:15]:
        tag = "측정" if r["measured"] else "가설"
        print(f"  [{r['count']:>3}|{tag}] {(r['sub_problem'] or '-'):20} {r['term']}")
    if not q:
        print("  (미해결 miss 없음 — 라이브러리 커버리지 양호)")


if __name__ == "__main__":
    main()