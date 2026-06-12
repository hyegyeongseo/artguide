"""pipeline/roadmap.py — 사용자 성장 로드맵(진척 레이어).

"포즈 1000개"보다 "왜 다음에 이걸 연습해야 하는가"가 중요하다는 방향에 맞춘 레이어.
LLM 없이 결정적으로 동작한다. taxonomy(practice_prompt/personas) + practice_log 만으로
'현재 단계 → 다음 연습 → 다음 목표'를 만든다.

커리큘럼 순서(CURRICULUM)는 '구조 먼저' 원칙을 인코딩한다:
  큰 구조(비율·무게·동세) → 사지(관절·단축) → 손 → 빛/명암 → 구도/색.
"왜 다음에 손을 연습하나" = 손 앞의 구조 단계가 어느 정도 자리잡은 뒤가 효과적이라는 것.

상태 전이(휴리스틱):
  new → practicing(1회 tried) → improving(2회+ / 최근 진단에서 약하게 뜸) → steady(3회+ & 최근 미검출)
모든 DB 작업은 예외를 삼켜 /roadmap·/practice 가 앱을 막지 않게 한다.
"""
from collections import defaultdict
from sqlalchemy import text, bindparam
from stores.db import engine
from pipeline.diagnose import taxonomy
from pipeline.profiles import resolve_profile, POSE_DEPENDENT, FIGURE_ORDER, ALL_AXES
from pipeline.growth_stage import estimate_stage

# 구조 먼저 → 디테일. 이 순서가 "다음 목표"의 사다리.
CURRICULUM = FIGURE_ORDER          # 단일 출처: profiles 의 인물 순서를 그대로(중복 정의 제거).
# 각 축의 구축 다이어그램(tools/gen_construction_diagrams.py 산출물 키와 1:1). 인물 10 + 풍경 4 = 14축
# 전부 construction/<sp>.svg 가 존재하므로 풍경 축도 diagram 키가 붙는다(예전엔 인물 축만 있었음).
DIAGRAM_KEY = {sp: sp for sp in ALL_AXES}

# 사용자 노출 문구용 한글 라벨(_why 등). 프론트 NextSteps.jsx 의 SUB_LABELS와 동일하게 유지.
LABELS = {
    "weight_balance": "무게중심",
    "foreshortening": "단축(투시)",
    "proportion": "비율",
    "action_line": "동세",
    "joint_articulation": "관절",
    "hand_structure": "손 구조",
    "value_structure": "명암",
    "composition_balance": "구도",
    "color_harmony": "색 조화",
    "light_direction": "빛 방향",
    "linear_perspective": "선원근",
    "atmospheric_perspective": "대기원근",
    "depth_layering": "공간 깊이",
    "horizon_placement": "지평선 배치",
}

STEADY_TRIES = 3
IMPROVING_TRIES = 2
RECUR_MIN = 2          # 진단에 이만큼 이상 떴고 아직 steady가 아니면 '자주 막히는 부분'
RECENT_N = 5           # '최근'으로 볼 업로드(=guide 호출) 회수. 방향이 바뀌면 옛 신호가 이 창 밖으로 빠진다.
GOAL_MIN_WINDOW = 2    # 목표 고정 후 최소 이만큼 업로드해야 '안 보임'으로 달성 인정(steady 졸업은 예외)


def record_practice(user_id, sub_problem, action, confidence=None, guide_id=None):
    """버튼/진단 이벤트를 기록. action ∈ {seen, tried, later}."""
    try:
        with engine.begin() as cx:
            cx.execute(text("""INSERT INTO practice_log
                (user_id, sub_problem, action, confidence, guide_id)
                VALUES (:u, :sp, :a, :c, :g)"""),
                dict(u=user_id or "anon", sp=sub_problem, a=action,
                     c=confidence, g=guide_id))
    except Exception as e:
        print(f"[roadmap] practice 기록 실패(무시): {type(e).__name__}: {e}")


def _history(user_id):
    """user_id의 sub_problem별 집계.

    - tries: 'tried' 전 기간 누적(노력은 사라지지 않음).
    - seen_recent / flag_count: **최근 RECENT_N회 업로드(guide_id)** 기준.
      "최근에 떴는가(flagged)"와 "재발 횟수"를 최근 창으로만 보므로, 사용자가 주제·스타일·방향을
      바꾸면 옛 신호가 창 밖으로 자연히 빠진다(→ 졸업(steady) 가능, 재발도 요즘 기준).
      seen_recent = 최근 창 안에서의 최신 confidence, flag_count = 최근 창에서 떴던 업로드 수.
    """
    tries = defaultdict(int)
    seen_recent = {}               # sub_problem -> 최근 창 안 최신 confidence(없으면 = 최근엔 미검출)
    flag_count = defaultdict(int)  # sub_problem -> 최근 창에서 떴던 업로드 수(재발 신호)
    trend = "new"                  # 최근 창에서 약점 수의 증감 방향(개선/악화/유지)
    timeline = []                  # 막대 차트용: 업로드별(예전→최근) 함께 짚은 약점 수
    try:
        with engine.begin() as cx:
            for sp, n in cx.execute(text(
                    "SELECT sub_problem, COUNT(*) FROM practice_log "
                    "WHERE user_id=:u AND action='tried' GROUP BY sub_problem"),
                    {"u": user_id}):
                tries[sp] = int(n)

            # 최근 N회 업로드(guide_id) — '한 번 그린 그림'의 단위. 최신순.
            recent_ids = [r[0] for r in cx.execute(text(
                "SELECT guide_id FROM practice_log "
                "WHERE user_id=:u AND action='seen' AND guide_id IS NOT NULL "
                "GROUP BY guide_id ORDER BY MAX(ts) DESC LIMIT :n"),
                {"u": user_id, "n": RECENT_N}).fetchall()]

            if recent_ids:
                stmt = text(
                    "SELECT sub_problem, guide_id, confidence, ts FROM practice_log "
                    "WHERE user_id=:u AND action='seen' AND guide_id IN :gids"
                ).bindparams(bindparam("gids", expanding=True))
                guides_by_sp = defaultdict(set)   # 재발: sub_problem이 뜬 '업로드' 집합
                flags_per_guide = defaultdict(set)  # 업로드(guide_id) -> 떴던 축 집합(→ trend)
                latest = {}                       # sub_problem -> (ts, confidence)
                for sp, gid, conf, ts in cx.execute(stmt, {"u": user_id, "gids": recent_ids}):
                    guides_by_sp[sp].add(gid)
                    flags_per_guide[gid].add(sp)
                    if sp not in latest or ts > latest[sp][0]:
                        latest[sp] = (ts, conf)
                for sp, guides in guides_by_sp.items():
                    flag_count[sp] = len(guides)
                for sp, (_, conf) in latest.items():
                    seen_recent[sp] = conf
                trend = _trend_from(recent_ids, flags_per_guide)  # delta3: 약점 수 증감 방향
                # 막대 차트용 — 업로드별(예전→최근) 함께 짚은 약점 축 수 시계열.
                timeline = [{"flagged_count": len(flags_per_guide.get(g, ()))}
                            for g in reversed(recent_ids)]
    except Exception as e:
        print(f"[roadmap] 이력 집계 실패(무시, 빈 이력): {type(e).__name__}: {e}")
    return tries, seen_recent, flag_count, trend, timeline


def _trend_from(recent_ids, flags_per_guide):
    """delta3 — 최근 창에서 '업로드당 약점 수'가 줄고 있나/늘고 있나(판정 아님, 방향만).

    recent_ids 는 최신순. 최신 절반 vs 예전 절반의 평균 약점 수를 비교한다. 표본이 적으면 'new'.
    decreasing = 약점이 줄어드는 방향(개선 신호), increasing = 늘어나는 방향, steady = 비슷.
    """
    n = len(recent_ids)
    if n < 3:
        return "new"
    half = n // 2
    newer, older = recent_ids[:half], recent_ids[half:]
    a = sum(len(flags_per_guide.get(g, ())) for g in newer) / max(len(newer), 1)
    b = sum(len(flags_per_guide.get(g, ())) for g in older) / max(len(older), 1)
    if a < b - 0.5:
        return "decreasing"
    if a > b + 0.5:
        return "increasing"
    return "steady"


def _status(sp, tries, seen_recent):
    t = tries.get(sp, 0)
    flagged = sp in seen_recent     # 최근 진단에서 아직 약점으로 떴는가
    if t >= STEADY_TRIES and not flagged:
        return "steady"
    if t >= IMPROVING_TRIES:
        return "improving"
    if t >= 1:
        return "practicing"
    return "new"


def _step(sp, tax):
    e = tax.get(sp, {})
    return {
        "sub_problem": sp,
        "practice_prompt": e.get("practice_prompt", ""),
        "what_to_observe": e.get("what_to_observe", ""),
        "diagram": DIAGRAM_KEY.get(sp),          # 프론트가 construction/<diagram>.svg 로드
        "reference_query": e.get("reference_query", ""),
    }


def _peer_active(sp, seen_recent):
    """delta2 — 같은 포즈군(POSE_DEPENDENT) 동료 축이 최근 떴는가.

    어떤 포즈 의존 축이 최근 안 떴을 때 그게 '해결'인지 '주제 전환(인물을 안 그림)'인지 구분하는 신호.
    동료가 활성(peer_active=True)인데 이 축만 잠잠 → 해결 쪽. 동료도 다 잠잠 → 주제가 바뀐 것일 수 있음.
    포즈 비의존 축(구도·색 등)엔 의미 없어 None.
    """
    if sp not in POSE_DEPENDENT:
        return None
    return any(p in seen_recent for p in POSE_DEPENDENT if p != sp)


def _focus_and_next(tries, seen_recent, flag_count, curriculum=CURRICULUM):
    """'지금 집중할 축'과 '다음 목표'를 커리큘럼 + 이력으로 결정(get_roadmap·growth_context 공용).

    현재 단계: 아직 steady가 아닌 것 중 (1) 최근 진단에 뜬 것 우선, 없으면 (2) 커리큘럼 앞쪽.
      뜬 것이 여럿이면 delta1 — **재발 빈도(flag_count) 높은 것 우선**, 동순위는 커리큘럼 순서(구조 먼저).
    다음 목표: 커리큘럼에서 현재 다음으로 아직 steady가 아닌 축.
    curriculum은 track 프로파일에서 옴(인물·풍경이 다른 순서).
    """
    statuses = {sp: _status(sp, tries, seen_recent) for sp in curriculum}
    not_steady = [sp for sp in curriculum if statuses[sp] != "steady"]
    flagged = [sp for sp in not_steady if sp in seen_recent]
    if flagged:
        # delta1: 최근 가장 자주 막힌 것 우선 → 동순위면 커리큘럼 순서(구조 먼저)로 타이브레이크.
        flagged.sort(key=lambda sp: (-flag_count.get(sp, 0), curriculum.index(sp)))
        pool = flagged
    else:
        pool = not_steady
    current_sp = pool[0] if pool else curriculum[-1]
    idx = curriculum.index(current_sp)
    nxt = next((sp for sp in curriculum[idx + 1:] if statuses[sp] != "steady"), None)
    return current_sp, nxt, statuses


# ── N장 기준 목표 고정/진급 레이어 ────────────────────────────────────────────
# 기존 _focus_and_next 는 '매 호출 재계산기'다. 그 위에 목표를 한 번 고정(pin)하고
# 'N장 동안 그 약점이 안 보이면 달성 → 다음 축으로 진급'하는 진행 시스템을 얹는다.
# 표(user_goal)가 없거나 오류면 전부 None 으로 폴백 → 기존 동작 그대로(무해).
_goal_table_ready = False


def _ensure_goal_table():
    """user_goal 테이블 보장(프로세스당 1회, 멱등). 마이그레이션 미적용 환경도 자동 동작."""
    global _goal_table_ready
    if _goal_table_ready:
        return
    try:
        with engine.begin() as cx:
            cx.execute(text(
                "CREATE TABLE IF NOT EXISTS user_goal ("
                " user_id VARCHAR(64) NOT NULL,"
                " track VARCHAR(32) NOT NULL DEFAULT '',"
                " sub_problem VARCHAR(48) NOT NULL,"
                " baseline_count INT NOT NULL DEFAULT 0,"
                " set_seq INT NOT NULL DEFAULT 0,"
                " prev_achieved VARCHAR(48) NULL,"
                " advanced_seq INT NULL,"
                " updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
                " PRIMARY KEY (user_id, track))"))
        _goal_table_ready = True
    except Exception as e:
        print(f"[roadmap] user_goal 준비 실패(무시): {type(e).__name__}: {e}")


def _upload_seq(cx, user_id):
    """지금까지의 누적 업로드 수(서로 다른 guide_id 수) = N장 창의 좌표."""
    r = cx.execute(text("SELECT COUNT(DISTINCT guide_id) FROM practice_log "
                        "WHERE user_id=:u AND action='seen' AND guide_id IS NOT NULL"),
                   {"u": user_id}).scalar()
    return int(r or 0)


def _next_curriculum(sp, curriculum, statuses):
    """sp 다음으로 아직 steady가 아닌 커리큘럼 축(없으면 남은 첫 축, 그것도 없으면 마지막)."""
    if sp in curriculum:
        idx = curriculum.index(sp)
        nxt = next((x for x in curriculum[idx + 1:] if statuses.get(x) != "steady"), None)
        if nxt:
            return nxt
    return next((x for x in curriculum if statuses.get(x) != "steady"), curriculum[-1])


def _resolve_goal(user_id, track, curriculum, statuses, seen_recent, flag_count, candidate_sp):
    """목표를 고정/평가/진급하고 활성 목표 dict 반환. 실패/표없음 → None(기존 동작 유지).

    - 첫 목표: 지금 후보(candidate_sp)가 '실제 약점'(flagged/재발)일 때만 고정. 안 그러면 None.
    - 달성: 그 축이 steady 졸업했거나, 고정 후 GOAL_MIN_WINDOW장 이상 지났는데 최근 창에서 안 보임.
    - 진급: 달성 시 커리큘럼상 다음 not-steady 축으로 목표 교체. 실제로 막혔던(baseline>0) 경우만 '달성' 셀러브레이션.
    """
    _ensure_goal_table()
    tkey = track or ""
    try:
        with engine.begin() as cx:
            seq = _upload_seq(cx, user_id)
            row = cx.execute(text(
                "SELECT sub_problem, baseline_count, set_seq, prev_achieved, advanced_seq "
                "FROM user_goal WHERE user_id=:u AND track=:t"),
                {"u": user_id, "t": tkey}).fetchone()

            def _set(sp, prev, adv):
                cx.execute(text(
                    "INSERT INTO user_goal "
                    "(user_id,track,sub_problem,baseline_count,set_seq,prev_achieved,advanced_seq) "
                    "VALUES (:u,:t,:sp,:b,:s,:p,:a) "
                    "ON DUPLICATE KEY UPDATE sub_problem=:sp, baseline_count=:b, "
                    "set_seq=:s, prev_achieved=:p, advanced_seq=:a"),
                    {"u": user_id, "t": tkey, "sp": sp, "b": flag_count.get(sp, 0),
                     "s": seq, "p": prev, "a": adv})

            def _out(sp, status, baseline, set_seq, just, prev):
                return {"sub_problem": sp, "status": status,
                        "baseline_count": int(baseline), "current_count": flag_count.get(sp, 0),
                        "uploads_since": max(0, seq - int(set_seq)),
                        "just_achieved": bool(just), "prev_achieved": prev}

            # 첫 목표 — '실제 약점'일 때만 고정(커리큘럼 체크박스로 행진하지 않게)
            if row is None:
                if not candidate_sp or (flag_count.get(candidate_sp, 0) == 0
                                        and candidate_sp not in seen_recent):
                    return None
                _set(candidate_sp, None, None)
                return _out(candidate_sp, "in_progress", flag_count.get(candidate_sp, 0), seq, False, None)

            gsp, baseline, set_seq, prev_ach, adv_seq = row
            uploads_since = seq - int(set_seq)
            is_steady = statuses.get(gsp) == "steady"
            stopped = gsp not in seen_recent                     # 최근 창에서 더 이상 안 뜸
            achieved = is_steady or (uploads_since >= GOAL_MIN_WINDOW and stopped)

            if achieved:
                nxt = _next_curriculum(gsp, curriculum, statuses)
                celebrate = int(baseline) > 0                    # 실제로 막혔던 축만 '달성' 표시
                if nxt and nxt != gsp:
                    _set(nxt, gsp if celebrate else None, seq)
                    return _out(nxt, "in_progress", flag_count.get(nxt, 0), seq,
                                celebrate, gsp if celebrate else None)
                # 더 갈 곳 없음(전부 steady) → 목표 완료 상태로 종료
                return _out(gsp, "achieved", baseline, set_seq,
                            (adv_seq != seq), prev_ach)

            # 진행 중 — just_achieved 는 직전 진급이 '이번 업로드'에 일어났는지
            return _out(gsp, "in_progress", baseline, set_seq,
                        adv_seq is not None and int(adv_seq) == seq, prev_ach)
    except Exception as e:
        print(f"[roadmap] goal 처리 실패(무시, 목표 비활성): {type(e).__name__}: {e}")
        return None


def get_roadmap(user_id="anon", track=None, degraded=False):
    """현재 단계 → 다음 연습 → 다음 목표 + 전체 사다리(상태 포함). track 프로파일의 커리큘럼 기준.

    degraded=True면 포즈 의존 축을 제외하고 본다(이미지가 함께 온 경우). 표준 /roadmap 호출은
    이미지가 없어 degraded=False → 전체 커리큘럼(장기 그림)을 그대로 보여준다.
    """
    tax = taxonomy()
    curriculum = resolve_profile(track)["curriculum"]
    exclude = POSE_DEPENDENT if degraded else frozenset()
    cur = [sp for sp in curriculum if sp not in exclude] or list(curriculum)
    tries, seen_recent, flag_count, trend, timeline = _history(user_id)
    current_sp, nxt, statuses = _focus_and_next(tries, seen_recent, flag_count, cur)

    # N장 기준 목표 고정/진급(실패 시 None → 기존 재계산 동작 유지).
    goal = _resolve_goal(user_id, track, cur, statuses, seen_recent, flag_count, current_sp)
    if goal and goal["status"] == "in_progress":
        current_sp = goal["sub_problem"]                       # 고정 목표로 노출 안정화(흔들림 방지)
        nx = _next_curriculum(current_sp, cur, statuses)
        nxt = nx if nx != current_sp else None

    ladder = []
    for sp in cur:
        st = statuses[sp]
        ladder.append({"sub_problem": sp, "status": st,
                       "tries": tries.get(sp, 0),
                       "flagged": sp in seen_recent,
                       # 자주 막히는 부분: 진단에 RECUR_MIN회+ 떴는데 아직 안정화 안 됨.
                       "recurring": flag_count.get(sp, 0) >= RECUR_MIN and st != "steady",
                       "peer_active": _peer_active(sp, seen_recent),  # delta2: 해결 vs 주제전환 단서
                       "flag_count": flag_count.get(sp, 0)})

    done = sum(1 for r in ladder if r["status"] == "steady")
    return {
        "user_id": user_id,
        "track": track,
        "current": _step(current_sp, tax),                     # 지금 집중
        "next_practice": tax.get(current_sp, {}).get("practice_prompt", ""),  # 바로 할 연습
        "next_goal": _step(nxt, tax) if nxt else None,         # 다음 목표
        "progress": {"steady": done, "total": len(cur)},
        "ladder": ladder,
        "recurring": [r["sub_problem"] for r in ladder if r["recurring"]],  # 자주 막히는 부분
        "trend": trend,                                                      # delta3: 약점 수 증감 방향
        "timeline": timeline,                                                # 막대용: 업로드별(예전→최근) 약점 수
        "goal": goal,                                                        # N장 기준 고정 목표(진행/달성/진급)
        "why": _why(current_sp, nxt),
    }


def growth_context(user_id="anon", track=None, curriculum=None, degraded=False):
    """가이드 파이프라인이 쓰는 '압축 이력'. 진단 랭킹·프롬프트·응답분기로 흘러간다.

    LLM 없이 결정적. DB가 없거나 이력이 비면 빈 컨텍스트로 안전하게 폴백한다
    (콜드스타트 = current_focus는 커리큘럼 첫 단계, recurring 없음).
    스키마에 의존하지 않도록 순수 dict만 반환한다(타입 변환은 호출부에서).
    curriculum을 직접 주면 그걸 쓴다(호출부가 scene으로 이미 프로파일을 정한 경우 — 진단과 일치 보장).
    없으면 track으로 해석(scene 없음 → 기본 레인).
    degraded=True(이번 업로드에서 전신 미검출)면 포즈 의존 축을 focus·recurring·steady에서 제외한다
      (applicability-aware): '이 그림으론 못 보는 축'을 지금 집중/재발로 들지 않게. 진단의 중재와 일치.
    """
    curriculum = curriculum or resolve_profile(track)["curriculum"]
    exclude = POSE_DEPENDENT if degraded else frozenset()
    cur = [sp for sp in curriculum if sp not in exclude] or list(curriculum)
    try:
        tries, seen_recent, flag_count, trend, _timeline = _history(user_id)
        current_sp, nxt, statuses = _focus_and_next(tries, seen_recent, flag_count, cur)
        steady = [sp for sp in cur if statuses[sp] == "steady"]
        recurring = [sp for sp in cur
                     if flag_count.get(sp, 0) >= RECUR_MIN and statuses[sp] != "steady"]
        # 콜드스타트 여부(첫 업로드: 연습/노출 이력 사실상 없음) → main 이 그림 기반 진입점 교정에 사용.
        total_tries = sum(tries.values())
        cold = (total_tries == 0 and not seen_recent)
        # 내부 성장 단계(노출 금지 — apply_cold_start·톤 힌트 전용. '_' 접두로 비노출 표식).
        stage, _ratio = estimate_stage(len(steady), len(cur), trend, total_tries)
        return {"user_id": user_id, "steady": steady, "recurring": recurring,
                "current_focus": current_sp, "next_goal": nxt,
                "trend": trend, "why": _why(current_sp, nxt),
                "cold": cold, "_stage": stage}
    except Exception as e:
        print(f"[roadmap] growth_context 실패(무시, 빈 컨텍스트): {type(e).__name__}: {e}")
        return {"user_id": user_id, "steady": [], "recurring": [],
                "current_focus": None, "next_goal": None, "trend": "new", "why": "",
                "cold": True, "_stage": estimate_stage(0, 1)[0]}


def _why(current_sp, nxt):
    """'왜 지금 이걸, 다음에 저걸'에 대한 한 줄 설명(구조 먼저 원칙). 내부 id 대신 한글 라벨 노출."""
    cur = LABELS.get(current_sp, current_sp)
    msg = f"지금은 '{cur}'에 집중하면 좋아요 — 커리큘럼에서 아직 자리잡지 않은 단계예요."
    if nxt:
        msg += f" 이게 안정되면 다음은 '{LABELS.get(nxt, nxt)}' 단계로 넘어가면 자연스럽습니다."
    return msg
