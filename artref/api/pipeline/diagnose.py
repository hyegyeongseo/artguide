import os, yaml, numpy as np
from functools import lru_cache
from pipeline.profiles import POSE_DEPENDENT

# 파일 위치 기준 → repo 루트/CWD 어디서 실행해도 동작(eval 포함). 환경변수로 override 가능.
TAXONOMY_PATH = os.environ.get(
    "TAXONOMY_PATH",
    os.path.join(os.path.dirname(__file__), "..", "schema", "taxonomy.yaml"),
)

@lru_cache
def taxonomy():
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return {e["id"]: e for e in yaml.safe_load(f)}

NOSE = 0
L_SH, R_SH, L_HIP, R_HIP = 11, 12, 23, 24
L_EL, R_EL, L_WR, R_WR = 13, 14, 15, 16
L_KN, R_KN, L_AN, R_AN = 25, 26, 27, 28
REGION_KP = {
  "weight_balance": ["left_hip", "right_hip", "left_ankle", "right_ankle"],
  "foreshortening": ["left_wrist", "right_wrist", "left_elbow", "right_elbow"],
  "proportion": ["nose", "left_ankle", "right_ankle"],
  "action_line": ["nose", "left_hip", "right_hip"],
  "joint_articulation": ["left_elbow", "right_elbow", "left_knee", "right_knee"],
}

def _xy(kp, i): return np.array(kp[i][:2])

def _angle(kp, a, b, c):
    ba, bc = _xy(kp, a) - _xy(kp, b), _xy(kp, c) - _xy(kp, b)
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))

def pose_signals(kp):
    sh_c = (_xy(kp, L_SH) + _xy(kp, R_SH)) / 2
    hp_c = (_xy(kp, L_HIP) + _xy(kp, R_HIP)) / 2
    com = (sh_c + hp_c) / 2
    feet = (_xy(kp, L_AN) + _xy(kp, R_AN)) / 2
    base = abs(kp[L_AN][0] - kp[R_AN][0]) or 0.05
    torso = np.linalg.norm(sh_c - hp_c) or 1e-6
    legs = (np.linalg.norm(_xy(kp, L_HIP) - _xy(kp, L_AN)) +
            np.linalg.norm(_xy(kp, R_HIP) - _xy(kp, R_AN))) / 2
    armL = np.linalg.norm(_xy(kp, L_SH) - _xy(kp, L_WR))
    armR = np.linalg.norm(_xy(kp, R_SH) - _xy(kp, R_WR))
    return {
      "com_offset": float(abs(com[0] - feet[0]) / base),
      "torso_lean": float(abs(sh_c[0] - hp_c[0])),
      "leg_torso_ratio": float(legs / torso),
      "arm_proj_ratio": float(min(armL, armR) / max(armL, armR)) if max(armL, armR) else 1.0,
      "elbow_angle_min": min(_angle(kp, L_SH, L_EL, L_WR), _angle(kp, R_SH, R_EL, R_WR)),
      "knee_angle_min": min(_angle(kp, L_HIP, L_KN, L_AN), _angle(kp, R_HIP, R_KN, R_AN)),
    }

def image_signals(pil):
    g = np.asarray(pil.convert("L"), float) / 255
    ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    w = g.sum() + 1e-9
    cx, cy = (xs * g).sum() / w / g.shape[1], (ys * g).sum() / w / g.shape[0]
    return {"value_std": float(g.std()),
            "focus_centeredness": float(1 - 2 * max(abs(cx - 0.5), abs(cy - 0.5)))}


# ── 색/빛/손 신호(Phase: 자동 측정 3종 연결) ──────────────────────────────────────────────
# 전부 *보수적* 이다(임계 드물게 발화 + 낮은 confidence → 약하면 가설형으로). 임계값은 대략값이라
# eval/튜닝(threshold sweep)으로 재조정 대상. 단색/빈 캔버스(분산≈0)는 노이즈라 신호를 내지 않는다.
def color_signals(pil):
    """채도 평균 + 색상 분산(채도 가중 원형 분산). 거의 단색이면 빈 dict."""
    g = np.asarray(pil.convert("L"), float) / 255
    if float(g.std()) < 1e-3:
        return {}
    hsv = np.asarray(pil.convert("HSV"), float)
    H, S = hsv[..., 0] / 255.0, hsv[..., 1] / 255.0
    sat_mean = float(S.mean())
    ang = H * 2 * np.pi
    w = S + 1e-6
    cx = float((np.cos(ang) * w).sum() / w.sum())
    cy = float((np.sin(ang) * w).sum() / w.sum())
    R = float(np.hypot(cx, cy))            # 1=색상 집중, 0=넓게 퍼짐
    return {"sat_mean": sat_mean, "hue_spread": float(1 - R)}


def light_signals(pil, pose):
    """저주파 휘도 '램프'(한 방향 광원이면 전반적 밝기 기울기↑, 평면조명이면 ≈0). 인물 bbox 우선."""
    g = np.asarray(pil.convert("L"), float) / 255
    if float(g.std()) < 1e-3:
        return {}
    mask = _figure_bbox(pose, g.shape) if pose.get("status") == "ok" else None
    if mask is not None:
        ys, xs = np.where(mask)
        if ys.size and xs.size:
            g = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if g.shape[0] < 4 or g.shape[1] < 4:
        return {}
    from PIL import Image as _Img
    small = np.asarray(_Img.fromarray((g * 255).astype("uint8")).resize((16, 16)), float) / 255
    gy, gx = np.gradient(small)
    ramp = float(np.hypot(gx.mean(), gy.mean()))   # 순(net) 방향성 밝기 변화
    return {"light_ramp": ramp}


def landscape_signals(pil):
    """풍경 전용 image 신호(비인물 track에서만 surface — 인물 track은 profile 게이팅으로 제외).

    - depth_contrast_falloff: 근경(아래 1/3) 국소대비 − 원경(위 1/3) 국소대비. 클수록 거리에 따른
      약화가 뚜렷(대기원근 양호), ≈0/음수면 원경이 근경만큼 또렷 → 깊이 평면적.
    - horizon_y: 가장 강한 수평 명도 전이 행의 정규화 위치(지평선 근사). 0.5 부근이면 정중앙.
    단색/빈 캔버스(분산≈0)는 빈 dict.
    """
    g = np.asarray(pil.convert("L"), float) / 255
    if float(g.std()) < 1e-3:
        return {}
    H = g.shape[0]
    if H < 6:
        return {}
    top, bot = g[:H // 3], g[2 * H // 3:]
    falloff = float(bot.std() - top.std())
    rowmean = g.mean(axis=1)
    steps = np.abs(np.diff(rowmean))
    horizon_y = float((int(np.argmax(steps)) + 1) / H) if steps.size else 0.5
    return {"depth_contrast_falloff": falloff, "horizon_y": horizon_y}


def hand_signals(pil):
    """손 구조 신호 — ml/hands 연결. HAND_AUTO 환경변수가 켜졌을 때만 동작(손 레퍼런스 적재 후 켤 것).

    기본 OFF: hands.py 경고대로 region=hand 레퍼런스가 없으면 손 신호가 떠도 검색이 전부 miss 라,
    라이브러리 보강 전까지는 자동 발화를 끈다(앱 동작·기존 eval 불변). 모델/런타임 없으면 조용히 skip.
    """
    import os
    if os.environ.get("HAND_AUTO", "0").lower() not in ("1", "true", "yes"):
        return {}
    try:
        from ml.hands import detect, hand_signal
        h = detect(pil)
        if not h.get("available"):
            return {}
        conf, sig = hand_signal(h["hands"])
        if conf > 0:
            return {"_hand": (round(float(conf), 2), sig)}
    except Exception as e:
        print(f"[diagnose] 손 신호 실패(무시): {type(e).__name__}: {e}")
    return {}

VIS_KP = 0.3  # 개별 키포인트 가시성 하한(bbox 계산용; 파일 평균 VIS와 별개)

def _figure_bbox(pose, shape):
    """가시 키포인트(정규화)로 인물 영역 bbox 마스크. 의미 없는 경우 None(전역으로 폴백)."""
    kp = pose.get("keypoints")
    if not kp:
        return None
    H, W = shape
    pts = [(x, y) for (x, y, v) in kp if v >= VIS_KP and 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0]
    if len(pts) < 6:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    pad = 0.08
    x0, x1 = max(0.0, min(xs) - pad), min(1.0, max(xs) + pad)
    y0, y1 = max(0.0, min(ys) - pad), min(1.0, max(ys) + pad)
    area = (x1 - x0) * (y1 - y0)
    # 너무 작거나(노이즈) 화면을 거의 채우면(분리 측정 의미 없음) None
    if (x1 - x0) < 0.10 or (y1 - y0) < 0.15 or area > 0.85:
        return None
    mask = np.zeros((H, W), bool)
    mask[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = True
    return mask

def region_signals(pil, pose):
    """Tier-2: 인물 영역 vs 배경의 국소 명도 분석. 포즈 없으면/모호하면 빈 dict(전역으로 폴백).
    - figure_value_range: 인물 '안'의 명도 폭(어두운 배경에 속지 않아 전역 value_std보다 정확).
    - figure_bg_contrast: 인물과 배경의 평균 명도차(작으면 실루엣이 배경과 섞임)."""
    if pose.get("status") != "ok":
        return {}
    g = np.asarray(pil.convert("L"), float) / 255
    mask = _figure_bbox(pose, g.shape)
    if mask is None:
        return {}
    fig, bg = g[mask], g[~mask]
    if fig.size < 50 or bg.size < 50:
        return {}
    lo, hi = np.percentile(fig, [10, 90])
    return {"figure_value_range": float(hi - lo),
            "figure_bg_contrast": float(abs(fig.mean() - bg.mean()))}

# ── 진단 스코어러 임계값(중앙 집중 — eval/튜닝으로 재조정 가능) ─────────────────────────────
# 기본값은 기존 동작과 *정확히 동일*. scripts/tune_thresholds.py 가 이 dict 를 override 해 sweep 한다.
# DX_THRESHOLDS 환경변수(JSON)로도 덮어쓸 수 있다(재배포 없이 실험). proportion 은 단일 임계가 아니라
# track norm band(profiles._NORM_*)로 튜닝하므로 여기 없음.
_DEFAULT_THRESHOLDS = {
    "weight_balance.com_offset": 0.9,             # > 이면 발화
    "foreshortening.arm_proj_ratio": 0.6,         # < 이면 발화
    "action_line.torso_lean": 0.03,               # < 이면 발화(거의 직립)
    "joint_articulation.angle_max": 177.0,        # > 이면 발화(과신전)
    "value_structure.figure_value_range": 0.35,   # < 이면 발화(국소 명도폭)
    "value_structure.value_std": 0.16,            # < 이면 발화(전역 폴백)
    "value_structure.figure_bg_contrast": 0.08,   # < 이면 발화(실루엣-배경 섞임)
    "composition_balance.focus_centeredness": 0.9,  # > 이면 발화(정중앙)
    "color_harmony.sat_mean": 0.6,                # AND
    "color_harmony.hue_spread": 0.55,             # AND (둘 다 > 이면 발화)
    "light_direction.light_ramp": 0.015,          # < 이면 발화(평면 조명)
    "atmospheric_perspective.falloff_min": 0.02,  # < 이면 발화(원근 대비 약화 약함 = 깊이 평면적)
    "horizon_placement.center_half": 0.06,        # |horizon_y-0.5| < 이면 발화(지평선 정중앙)
}
THRESHOLDS = dict(_DEFAULT_THRESHOLDS)


def _load_env_thresholds():
    raw = os.environ.get("DX_THRESHOLDS")
    if not raw:
        return
    try:
        THRESHOLDS.update({k: float(v) for k, v in __import__("json").loads(raw).items()
                           if k in THRESHOLDS})
    except Exception as e:
        print(f"[diagnose] DX_THRESHOLDS 파싱 실패(무시): {type(e).__name__}: {e}")


_load_env_thresholds()


def apply_thresholds(overrides):
    """튜닝 하니스용: 임계값 일부를 덮어쓴다. 반환=이전 값(복원용)."""
    prev = {k: THRESHOLDS[k] for k in overrides if k in THRESHOLDS}
    THRESHOLDS.update({k: float(v) for k, v in overrides.items() if k in THRESHOLDS})
    return prev


def reset_thresholds():
    THRESHOLDS.clear(); THRESHOLDS.update(_DEFAULT_THRESHOLDS); _load_env_thresholds()


def _T(key):
    return THRESHOLDS[key]


def s_weight_balance(s):
    o = s.get("com_offset"); t = _T("weight_balance.com_offset")
    if o and o > t: return (min(0.65, 0.3 + 0.35 * (o - t)), f"무게중심이 지지면 밖 ≈ {o:.1f}배")
def s_foreshortening(s):
    r = s.get("arm_proj_ratio"); t = _T("foreshortening.arm_proj_ratio")
    if r is not None and r < t: return (min(0.6, 0.3 + 0.5 * (t - r)), f"좌우 팔 투영 길이비 ≈ {r:.2f}")
def s_proportion(s):
    r = s.get("leg_torso_ratio")
    band = (s.get("_norms") or {}).get("leg_torso", (0.75, 1.7))  # track norm; None이면 발화 끔
    if r is not None and band and (r < band[0] or r > band[1]):
        return (0.3, f"다리/몸통 길이비 ≈ {r:.2f}")
def s_action_line(s):
    l = s.get("torso_lean"); t = _T("action_line.torso_lean")
    if l is not None and l < t: return (0.3, f"몸통 기울기 ≈ {l:.02f} (거의 직립)")
def s_joint_articulation(s):
    vs = [v for v in (s.get("elbow_angle_min"), s.get("knee_angle_min")) if v is not None]
    if vs and max(vs) > _T("joint_articulation.angle_max"):
        return (0.4, "팔꿈치/무릎이 거의 완전히 펴짐(과신전 의심)")
def s_value_structure(s):
    """명도 구조 — 국소 측정(인물 명도폭 / 실루엣-배경 분리) 우선, 없으면 전역 value_std 폴백."""
    parts, conf = [], 0.0
    fr = s.get("figure_value_range")
    if fr is not None:                       # 인물 내부 명도 폭(배경 대비에 속지 않음)
        t = _T("value_structure.figure_value_range")
        if fr < t:
            conf = max(conf, min(0.55, 0.3 + 0.4 * (t - fr)))
            parts.append(f"인물 영역의 밝은 곳과 어두운 곳 차이가 좁음(명도 폭 ≈ {fr:.2f})")
    else:                                    # 포즈 없을 때만 전역으로
        v = s.get("value_std")
        if v is not None and v < _T("value_structure.value_std"):
            conf = max(conf, 0.4)
            parts.append(f"화면 전체 명도 표준편차 ≈ {v:.2f} (대비 좁음)")
    bg = s.get("figure_bg_contrast"); tb = _T("value_structure.figure_bg_contrast")
    if bg is not None and bg < tb:           # 인물-배경 명도차 작음 → 실루엣이 배경과 섞임(보수적 임계)
        conf = max(conf, min(0.5, 0.3 + 0.5 * (tb - bg)))
        parts.append(f"인물과 배경의 명도 차가 작아(차 ≈ {bg:.2f}) 실루엣이 배경과 섞여 보임")
    if parts:
        return (round(conf, 2), "; ".join(parts))
def s_composition_balance(s):
    c = s.get("focus_centeredness")
    if c is not None and c > _T("composition_balance.focus_centeredness"):
        return (0.3, f"시선 무게가 거의 정중앙 ({c:.2f})")
def s_color_harmony(s):
    """채도가 전반적으로 높고 색상이 넓게 퍼져 색끼리 경쟁할 때만(보수적). 약하면 가설형으로 안내됨."""
    sm, hs = s.get("sat_mean"), s.get("hue_spread")
    if (sm is not None and hs is not None
            and sm > _T("color_harmony.sat_mean") and hs > _T("color_harmony.hue_spread")):
        return (0.3, f"채도가 전반적으로 높고(≈{sm:.2f}) 색상이 넓게 퍼져 있음")
def s_light_direction(s):
    """전반 밝기 변화가 작아 광원 방향이 평면적일 때만(보수적)."""
    r = s.get("light_ramp")
    if r is not None and r < _T("light_direction.light_ramp"):
        return (0.3, f"화면 전반의 밝기 변화가 작아(≈{r:.3f}) 광원 방향이 뚜렷하지 않음")
def s_hand_structure(s):
    """ml/hands 가 낸 손 신호(평면 방향/단축). HAND_AUTO 켜졌을 때만 채워짐(없으면 None)."""
    return s.get("_hand")
def s_atmospheric_perspective(s):
    """원근에 따른 대비 약화가 약할 때만(원경이 근경만큼 또렷 → 깊이 평면적). 풍경 track 전용(게이팅)."""
    f = s.get("depth_contrast_falloff")
    if f is not None and f < _T("atmospheric_perspective.falloff_min"):
        return (0.3, f"원경과 근경의 대비 차가 작아(차 ≈ {f:.2f}) 거리감이 평면적으로 보일 수 있음")
def s_horizon_placement(s):
    """지평선이 화면 세로 중앙 부근일 때만. 풍경 track 전용(게이팅)."""
    y = s.get("horizon_y")
    if y is not None and abs(y - 0.5) < _T("horizon_placement.center_half"):
        return (0.3, f"지평선이 화면 세로 중앙 부근({y:.2f})에 위치")

SCORERS = {"weight_balance": s_weight_balance, "foreshortening": s_foreshortening,
           "proportion": s_proportion, "action_line": s_action_line,
           "joint_articulation": s_joint_articulation, "value_structure": s_value_structure,
           "composition_balance": s_composition_balance,
           "color_harmony": s_color_harmony, "light_direction": s_light_direction,
           "hand_structure": s_hand_structure,
           "atmospheric_perspective": s_atmospheric_perspective,
           "horizon_placement": s_horizon_placement}

# 이력 기반 연속성 보정(growth가 있을 때만). 정렬 키에만 더하는 nudge — '표시 confidence'는
# 측정값 그대로 두어 가드레일/근거 규칙을 건드리지 않는다.
STEADY_DEMOTE = 0.12    # 이미 안정화된 축은 1순위에서 살짝 뒤로
RECUR_PROMOTE = 0.08    # 자주 막히는(재발) 축은 살짝 앞으로
FOCUS_PROMOTE = 0.05    # 커리큘럼상 '현재 집중' 축 살짝 앞으로


def diagnose(scene, pose, pil, personas, user_terms=(), growth=None, profile=None):
    tax = taxonomy()
    degraded = pose.get("status") != "ok"
    eligible = set((profile or {}).get("subproblems") or [])   # track 게이팅(비면 전체 허용)
    norms = (profile or {}).get("norms") or {}
    sig = {}
    if not degraded:
        sig.update(pose_signals(pose["keypoints"]))
    sig.update(image_signals(pil))
    sig.update(region_signals(pil, pose))   # Tier-2: 인물/배경 국소 명도(포즈 ok일 때만)
    sig.update(color_signals(pil))           # 색 조화(보수적 image 신호)
    sig.update(light_signals(pil, pose))     # 빛 방향(저주파 휘도 램프)
    sig.update(hand_signals(pil))            # 손 구조(HAND_AUTO일 때만 — ml/hands 연결)
    sig.update(landscape_signals(pil))       # 풍경 전용(대기원근·지평선) — figure track은 게이팅으로 제외
    sig["_norms"] = norms                    # 스코어러(예: s_proportion)가 track norm을 읽게

    hits = {}
    for sid, fn in SCORERS.items():
        r = fn(sig)
        if r: hits[sid] = r
    measured_ids = set(hits)                 # 자동 측정으로 잡힌 것 = 근거 있음
    for sid, e in tax.items():
        if sid in hits: continue
        if any(p in personas for p in e["personas"]) or sid in user_terms:
            # 측정 근거 없음 → signal 비움(내부 라벨이 사용자 문구로 새지 않게). 프롬프트가 measured=False를 보고
            # 결핍을 단정하지 않고 '함께 어디를 볼지'로만, 가설형으로 안내한다.
            hits[sid] = (0.25 if e.get("auto") else 0.15, "")

    # track 게이팅: 이 track에서 다루지 않는 항목은 제외(풍경에 포즈 항목이 새어 나오지 않게).
    if eligible:
        hits = {sid: v for sid, v in hits.items() if sid in eligible}

    ranked = sorted(hits.items(), key=lambda kv: -kv[1][0])
    # 이력 연속성 보정: steady는 뒤로, 재발/현재집중은 앞으로 — 정렬 키에만(표시 confidence 불변).
    recurring_set = set((growth or {}).get("recurring", []))
    if growth:
        steady_set = set(growth.get("steady", []))
        focus = growth.get("current_focus")

        def _nudge(sid):
            n = 0.0
            if sid in steady_set:
                n -= STEADY_DEMOTE
            if sid in recurring_set:
                n += RECUR_PROMOTE
            if sid == focus and not (degraded and sid in POSE_DEPENDENT):
                n += FOCUS_PROMOTE
            return n
        ranked.sort(key=lambda kv: -(kv[1][0] + _nudge(kv[0])))
    # 사용자가 칩으로 직접 고른 관심(user_terms)을 최우선 블록으로 — "동세를 물었는데 명도가
    # 나옴"으로 신뢰가 깎이는 것 방지. 신호가 약하면 confidence는 낮게 유지되어(0.15~0.25)
    # 블록 문구가 단정 대신 가설형이 됨(프롬프트 규칙). 강한 자동 신호는 2·3번 블록으로 남음.
    if user_terms:
        ranked.sort(key=lambda kv: kv[0] not in user_terms)  # 안정 정렬: user_terms를 앞으로
    ranked = ranked[:3]
    obs = []
    for sid, (conf, sigtext) in ranked:
        e = tax[sid]
        obs.append({"sub_problem": sid, "signal": sigtext, "measured": sid in measured_ids,
                    "confidence": round(conf, 2),
                    "recurred": sid in recurring_set,   # 최근에도 반복적으로 떴는가(연속성)
                    "from_user": sid in user_terms,     # 사용자가 칩/문구로 직접 고른 관심(중재 우선순위)
                    "region": REGION_KP.get(sid) if not degraded else None,
                    "what_to_observe": e["what_to_observe"],
                    "reference_query": e["reference_query"],
                    "practice_prompt": e["practice_prompt"]})
    return {"primary_focus": obs[0]["sub_problem"] if obs else None,
            "observations": obs, "degraded": degraded, "persona": personas}
