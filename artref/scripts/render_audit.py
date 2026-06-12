"""render_audit.py — self_render(3D 백본) 코퍼스가 부족한지/충분한지 한 번에 진단.

실행(컨테이너 안, /repo 기준):
    docker compose exec -w /repo api python scripts/render_audit.py

출력 전체를 그대로 복사해서 돌려주면 됩니다(아래 [PASTE BACK] 구간 포함 전부).
DB/Qdrant가 살아 있어야 하며, 읽기만 합니다(아무것도 안 바꿉니다).
"""
import sys, os, json, statistics
from collections import Counter, defaultdict

sys.path.insert(0, "api")  # /repo에서 실행 시 api 패키지 경로
from sqlalchemy import text
from stores.db import engine
from stores import vectors as vstore
from cache import text_vec
from pipeline.diagnose import taxonomy
from pipeline._searchlogic import CONSTRUCTION_PERSONAS, SOURCE_PREF

K = 8
MISS = float(os.environ.get("MISS_SCORE_MIN", "0.22"))  # search.py와 동일 기본값
SELF_RENDER_PERSONAS = {p for p, src in SOURCE_PREF.items() if src == "self_render"}


def hr(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ───────────────────────── 0. 환경 점검 ─────────────────────────
def section_env():
    hr("0. 환경 점검")
    with engine.begin() as cx:
        total = cx.execute(text("SELECT COUNT(*) FROM reference_images")).scalar() or 0
        by_src = list(cx.execute(text(
            "SELECT source_type, COUNT(*) FROM reference_images GROUP BY source_type")))
    print(f"reference_images 총 {total}건")
    for s, n in by_src:
        print(f"  - {s:12} {n}")
    sr = dict(by_src).get("self_render", 0)
    if sr == 0:
        print("\n[중단] self_render가 0건입니다. 먼저 render_batch.py로 적재하세요.")
        sys.exit(0)
    return sr


# ───────────────────────── 1. 공급 인벤토리 ─────────────────────────
def section_inventory():
    hr("1. 공급 인벤토리 (self_render, MySQL 기준)")
    region = Counter(); body = Counter(); gender = Counter(); category = Counter()
    azim = Counter(); elev = Counter(); persona_cnt = Counter()
    have_cols = True
    try:
        with engine.begin() as cx:
            rows = list(cx.execute(text(
                "SELECT region, category, body_type, gender, personas, render_params "
                "FROM reference_images WHERE source_type='self_render'")))
    except Exception as e:
        have_cols = False
        print(f"  (region/category 컬럼 조회 실패 — 마이그레이션 002 미적용 가능: "
              f"{type(e).__name__}) → render_params에서 가능한 것만 집계")
        with engine.begin() as cx:
            rows = [(None, None, None, None, p, rp) for p, rp in cx.execute(text(
                "SELECT personas, render_params FROM reference_images "
                "WHERE source_type='self_render'"))]

    for r in rows:
        rg, cat, bt, gd, personas, rp = r
        region[rg] += 1; category[cat] += 1; body[bt] += 1; gender[gd] += 1
        try:
            for p in (json.loads(personas) if personas else []):
                persona_cnt[p] += 1
        except Exception:
            pass
        try:
            d = json.loads(rp) if rp else {}
            azim[d.get("azimuth")] += 1
            elev[d.get("elevation")] += 1
            if bt is None:
                body[d.get("body_type")] += 1
            if gd is None:
                gender[d.get("gender")] += 1
        except Exception:
            pass

    def show(name, c):
        print(f"\n{name}:")
        for k, v in sorted(c.items(), key=lambda x: (-x[1], str(x[0]))):
            print(f"  {str(k):24} {v}")

    show("persona별", persona_cnt)
    show("region별", region)
    show("body_type별", body)
    show("gender별", gender)
    show("category별", category)
    show("azimuth별", azim)
    show("elevation별", elev)

    print("\n[자동 점검]")
    n_body = len([k for k in body if k])
    print(f"  체형 종류: {n_body}개" + ("  ← 2개 이하면 비율/해부 다양성 얇음" if n_body <= 2 else ""))
    styles = [k for k in body if k and any(s in str(k).lower() for s in ("anime", "chibi", "toon"))]
    print(f"  스타일형 체형(anime/chibi 등): {len(styles)}개"
          + ("  ← 0개면 애니/치비 사용자에 맞는 레퍼런스 없음(알려진 갭)" if not styles else ""))
    print(f"  hand region 보유: {region.get('hand', 0)}건 (수는 보지만 손가락 품질은 눈으로 확인 필요)")
    print("  ※ azimuth는 Qdrant payload엔 없고 MySQL에만 있음 → 현재 시점 단위 라우팅 불가(E단계 참고)")


# ───────────────────────── 2. 질의 배터리 프로브 ─────────────────────────
def variant_families(personas):
    fams = {"base": [""]}
    is_constr = bool(set(personas) & CONSTRUCTION_PERSONAS)
    if is_constr:
        fams["body"] = [" muscular male figure", " female figure", " heavy build"]
        fams["view"] = [" foreshortened toward camera", " seen from above",
                        " three quarter back view"]
        fams["style"] = [" anime style", " chibi proportions"]
    return fams


def probe(query, persona):
    must = {"commercial_ok": True}
    must_not = {"source_type": "ai_example"} if persona in CONSTRUCTION_PERSONAS else None
    try:
        hits = vstore.query(text_vec(query).tolist(), K, must=must, must_not=must_not)
    except Exception as e:
        return {"err": f"{type(e).__name__}: {e}"}
    sr = [h for h in hits if (h.meta or {}).get("source_type") == "self_render"]
    facets = {(h.meta.get("body_type"), h.meta.get("region"), h.meta.get("category"))
              for h in hits if h.meta}
    top = hits[0].score if hits else None
    return {"top": top, "miss": (top is None) or top < MISS,
            "top_sr": sr[0].score if sr else None,
            "sr_in_k": len(sr), "div": len(facets)}


def section_battery():
    hr("2. 질의 배터리 (축 × 변형군)")
    print(f"K={K}, MISS_SCORE_MIN={MISS}\n")
    tax = taxonomy()
    miss_samples = defaultdict(list)  # 축 -> [(query, top, sr_in_k)] (미스 표본)

    header = f"{'axis':20}{'target':7}{'family':7}{'n':>3}{'miss%':>7}{'topSR':>8}{'SR@K':>7}{'div':>6}"
    print(header); print("-" * len(header))

    verdicts = {}
    for sp, e in tax.items():
        seed = e.get("reference_query", "")
        personas = e.get("personas", [])
        if not seed or not personas:
            continue
        persona = personas[0]
        is_target = persona in SELF_RENDER_PERSONAS
        fams = variant_families(personas)

        per_family = {}
        all_rows = []
        for fam, mods in fams.items():
            rows = []
            for m in mods:
                q = seed + m
                r = probe(q, persona)
                if "err" in r:
                    print(f"{sp:20}  [질의 실패] {r['err']}")
                    continue
                rows.append(r)
                all_rows.append(r)
                if r["miss"]:
                    miss_samples[sp].append((q, r["top"], r["sr_in_k"]))
            if rows:
                per_family[fam] = rows

        def agg(rows):
            miss = sum(x["miss"] for x in rows) / len(rows)
            tsr = [x["top_sr"] for x in rows if x["top_sr"] is not None]
            return (miss,
                    statistics.mean(tsr) if tsr else 0.0,
                    sum(x["sr_in_k"] for x in rows) / len(rows),
                    sum(x["div"] for x in rows) / len(rows))

        tflag = "self" if is_target else " -"
        for fam, rows in per_family.items():
            miss, tsr, srk, div = agg(rows)
            print(f"{sp:20}{tflag:7}{fam:7}{len(rows):>3}{miss*100:>6.0f}%"
                  f"{tsr:>8.3f}{srk:>7.1f}{div:>6.1f}")

        # 축 전체 자동 등급(참고용) — self_render 대상 축만
        if is_target and all_rows:
            base = per_family.get("base", all_rows)
            bmiss, btsr, bsrk, bdiv = agg(base)
            omiss, otsr, osrk, odiv = agg(all_rows)
            if osrk < 1.0:
                v = "EMPTY"
            elif bmiss > 0.10 or btsr < MISS or bdiv <= 2:
                v = "THIN(기본부터 약함)"
            elif omiss - bmiss > 0.30:
                v = "THIN(서브케이스 절벽)"
            else:
                v = "OK"
            verdicts[sp] = v

    hr("2-1. 자동 사전판정 (self_render 대상 6축, 참고용)")
    for sp, v in verdicts.items():
        print(f"  {sp:20} → {v}")
    if not verdicts:
        print("  (대상 축 없음 — taxonomy/적재 상태 확인 필요)")

    hr("2-2. 미스 표본 (분별 D용 — 각 축 최대 3개)")
    if not miss_samples:
        print("  미스 없음(이 배터리 한정).")
    for sp, lst in miss_samples.items():
        print(f"\n[{sp}]")
        for q, top, srk in lst[:3]:
            ts = f"{top:.3f}" if top is not None else "None"
            print(f"  miss  top={ts:>6}  SR@K={srk}  ::  {q!r}")


# ───────────────────────── 3. 운영 텔레메트리(있으면) ─────────────────────────
def section_telemetry():
    hr("3. 운영 텔레메트리 (트래픽 있으면)")
    try:
        with engine.begin() as cx:
            shown = {sp: n for sp, n in cx.execute(text(
                "SELECT sub_problem, COUNT(*) FROM adoption_log "
                "WHERE event='shown' AND sub_problem IS NOT NULL GROUP BY sub_problem"))}
            pos = {sp: n for sp, n in cx.execute(text(
                "SELECT sub_problem, COUNT(*) FROM adoption_log "
                "WHERE event IN ('clicked','saved','liked') AND sub_problem IS NOT NULL "
                "GROUP BY sub_problem"))}
            miss_terms = list(cx.execute(text(
                "SELECT term, count FROM miss_log ORDER BY count DESC LIMIT 15")))
    except Exception as e:
        print(f"  (텔레메트리 조회 실패/미구성: {type(e).__name__}) — 트래픽 전이면 정상, 건너뜀")
        return
    if not shown:
        print("  노출 로그 없음 — 아직 트래픽 전이면 배터리(2)로만 판단합니다.")
    else:
        print(f"{'sub_problem':20}{'shown':>7}{'CTR':>8}")
        for sp, s in sorted(shown.items(), key=lambda x: -x[1]):
            ctr = pos.get(sp, 0) / s if s else 0
            print(f"{sp:20}{s:>7}{ctr*100:>7.0f}%")
    if miss_terms:
        print("\n실서비스 miss_log 상위:")
        for t, c in miss_terms:
            print(f"  {c:>5}  {t}")


def main():
    print("render_audit — self_render 코퍼스 부족/충분 진단")
    section_env()
    section_inventory()
    section_battery()
    section_telemetry()
    print("\n" + "#" * 72)
    print("# [PASTE BACK] 위 0~3 출력 전체를 그대로 복사해서 돌려주세요.")
    print("#" * 72)


if __name__ == "__main__":
    main()
