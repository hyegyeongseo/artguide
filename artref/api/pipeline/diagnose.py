import os, yaml, numpy as np
from functools import lru_cache

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

def s_weight_balance(s):
    o = s.get("com_offset")
    if o and o > 0.9: return (min(0.65, 0.3 + 0.35 * (o - 0.9)), f"무게중심이 지지면 밖 ≈ {o:.1f}배")
def s_foreshortening(s):
    r = s.get("arm_proj_ratio")
    if r is not None and r < 0.6: return (min(0.6, 0.3 + 0.5 * (0.6 - r)), f"좌우 팔 투영 길이비 ≈ {r:.2f}")
def s_proportion(s):
    r = s.get("leg_torso_ratio")
    if r is not None and (r < 0.75 or r > 1.7): return (0.3, f"다리/몸통 길이비 ≈ {r:.2f}")
def s_action_line(s):
    l = s.get("torso_lean")
    if l is not None and l < 0.03: return (0.3, f"몸통 기울기 ≈ {l:.02f} (거의 직립)")
def s_joint_articulation(s):
    vs = [v for v in (s.get("elbow_angle_min"), s.get("knee_angle_min")) if v is not None]
    if vs and max(vs) > 177: return (0.4, "팔꿈치/무릎이 거의 완전히 펴짐(과신전 의심)")
def s_value_structure(s):
    """명도 구조 — 국소 측정(인물 명도폭 / 실루엣-배경 분리) 우선, 없으면 전역 value_std 폴백."""
    parts, conf = [], 0.0
    fr = s.get("figure_value_range")
    if fr is not None:                       # 인물 내부 명도 폭(배경 대비에 속지 않음)
        if fr < 0.35:
            conf = max(conf, min(0.55, 0.3 + 0.4 * (0.35 - fr)))
            parts.append(f"인물 영역의 밝은 곳과 어두운 곳 차이가 좁음(명도 폭 ≈ {fr:.2f})")
    else:                                    # 포즈 없을 때만 전역으로
        v = s.get("value_std")
        if v is not None and v < 0.16:
            conf = max(conf, 0.4)
            parts.append(f"화면 전체 명도 표준편차 ≈ {v:.2f} (대비 좁음)")
    bg = s.get("figure_bg_contrast")
    if bg is not None and bg < 0.08:         # 인물-배경 명도차 작음 → 실루엣이 배경과 섞임(보수적 임계)
        conf = max(conf, min(0.5, 0.3 + 0.5 * (0.08 - bg)))
        parts.append(f"인물과 배경의 명도 차가 작아(차 ≈ {bg:.2f}) 실루엣이 배경과 섞여 보임")
    if parts:
        return (round(conf, 2), "; ".join(parts))
def s_composition_balance(s):
    c = s.get("focus_centeredness")
    if c is not None and c > 0.9: return (0.3, f"시선 무게가 거의 정중앙 ({c:.2f})")

SCORERS = {"weight_balance": s_weight_balance, "foreshortening": s_foreshortening,
           "proportion": s_proportion, "action_line": s_action_line,
           "joint_articulation": s_joint_articulation, "value_structure": s_value_structure,
           "composition_balance": s_composition_balance}

def diagnose(scene, pose, pil, personas, user_terms=()):
    tax = taxonomy()
    degraded = pose.get("status") != "ok"
    sig = {}
    if not degraded:
        sig.update(pose_signals(pose["keypoints"]))
    sig.update(image_signals(pil))
    sig.update(region_signals(pil, pose))   # Tier-2: 인물/배경 국소 명도(포즈 ok일 때만)

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

    ranked = sorted(hits.items(), key=lambda kv: -kv[1][0])
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
                    "region": REGION_KP.get(sid) if not degraded else None,
                    "what_to_observe": e["what_to_observe"],
                    "reference_query": e["reference_query"],
                    "practice_prompt": e["practice_prompt"]})
    return {"primary_focus": obs[0]["sub_problem"] if obs else None,
            "observations": obs, "degraded": degraded, "persona": personas}
