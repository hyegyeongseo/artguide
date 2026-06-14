"""eval_harness/hand_faithfulness.py — 손 VLM '충실도' 평가 (2단계).

지각(그림을 봤나)은 확인됐다. 이건 다른 질문: 본 게 *맞나*. 합성 변형으로 못 푼다(의미적) →
사람 라벨 vs VLM 관찰을 케이스별로 대조. 구조화 JSON(view·structure·foreshortening) 덕에 기계 비교 가능.

핵심 산출:
  - view / structure 정확도, foreshortening P/R/F1 (사람 라벨 기준)
  - 케이스별(손등/주먹/만화체/원근단축/...) 분해 — 어디서 약한지
  - 일관성(consistent) ↔ 정확성 상관 — 2회 일관성 게이트가 '신뢰 신호'로 유효한가
    (3단계 노출 게이트 'confidence>임계 → 노출'의 근거)

사용:
  라벨 템플릿:  python -m eval_harness.hand_faithfulness --init /repo/samples/handfaith
                → labels_template.json 생성. 사람이 view/structure/foreshortening/case_type 채움.
  평가 실행:    HAND_VLM=1 GEMINI_API_KEY=.. python -m eval_harness.hand_faithfulness \
                  /repo/samples/handfaith --labels /repo/samples/handfaith/labels.json
  로직 검증:    python -m eval_harness.hand_faithfulness --selftest   (키 불필요)
"""
import os
import sys
import json
import time
import glob

_EXT = (".jpg", ".jpeg", ".png", ".webp")
_VIEWS = ["손등", "손바닥", "옆면", "불확실"]
_STRUCT = ["입체", "평면", "혼합", "불확실"]


def _images(folder):
    out = []
    for e in _EXT:
        out += glob.glob(os.path.join(folder, "*" + e))
    return sorted(out)


def _norm(s):
    # ml.vision 의 손가락 정규화 재사용(없으면 그대로)
    try:
        from ml.vision import _norm as vn
        return vn(s)
    except Exception:
        return str(s).strip()


def _norm_set(lst):
    return {_norm(x) for x in (lst or []) if str(x).strip()}


def init_template(folder):
    """폴더의 이미지마다 빈 라벨 스텁을 stdout 으로 출력(사람이 채운다).

    /repo 가 컨테이너에 읽기전용 마운트라 파일을 직접 못 쓴다 → 순수 JSON 을 stdout 으로 내보내고,
    호스트에서 `> labels.json` 으로 저장한다(호스트는 쓰기 가능). 안내문은 stderr(리다이렉트 오염 방지).
    """
    imgs = _images(folder)
    if not imgs:
        print(f"이미지 없음: {folder}", file=sys.stderr)
        return
    tmpl = {}
    for p in imgs:
        tmpl[os.path.basename(p)] = {
            "case_type": "",                 # 손등/손바닥/주먹/집기/겹침/원근단축/만화체/러프/선화/완성작 ...
            "view": "",                      # 손등|손바닥|옆면|불확실
            "structure": "",                 # 입체|평면|혼합
            "foreshortening": [],            # 단축돼 보이는 손가락 목록(없으면 [])
            "hand_clear": True,              # 단일 손이 분명히 보이나(잘림/다수/가림이면 false)
        }
    print(json.dumps(tmpl, ensure_ascii=False, indent=2))   # stdout = 순수 JSON
    print(f"\n[{len(imgs)}장] 위 JSON 을 labels.json 으로 저장 후 view/structure/foreshortening/case_type 을 채우세요.\n"
          f"호스트에서 바로 저장:  docker compose exec ... --init {folder} > <폴더>/labels.json", file=sys.stderr)


def _view_match(vlm, gt):
    """'correct'|'wrong'|'abstain'. VLM이 불확실=기권(틀림 아님). gt 불확실/빈값은 평가 제외(skip)."""
    if not gt or gt == "불확실":
        return "skip"
    if vlm == "불확실":
        return "abstain"
    return "correct" if vlm == gt else "wrong"


def _fs_counts(vlm_set, gt_set):
    tp = len(vlm_set & gt_set)
    fp = len(vlm_set - gt_set)
    fn = len(gt_set - vlm_set)
    return tp, fp, fn


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f = (2 * p * r / (p + r)) if (p and r) else None
    return p, r, f


def evaluate(folder, labels, runner=None, sleep=0.0):
    """labels(dict: filename→gt) 의 각 이미지에 observe_hand → 라벨과 대조. rows + 집계 반환.
    sleep: 이미지 사이 대기(초). 무료 티어 분당 한도(429) 예방용 throttle."""
    if runner is None:
        os.environ.setdefault("HAND_VLM", "1")
        from ml.vision import observe_hand
        runner = observe_hand
    rows = []
    for idx, (fn, gt) in enumerate(labels.items()):
        if sleep and idx:
            time.sleep(sleep)
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            rows.append({"file": fn, "error": "missing_image"})
            continue
        try:
            o = runner(path)
        except Exception as e:
            rows.append({"file": fn, "error": f"{type(e).__name__}: {e}"})
            continue
        if not o:
            rows.append({"file": fn, "error": "no_observation(gate/key/fail)"})
            continue
        vfs, gfs = _norm_set(o.get("foreshortening")), _norm_set(gt.get("foreshortening"))
        tp, fp, fn_ = _fs_counts(vfs, gfs)
        rows.append({
            "file": fn,
            "case_type": gt.get("case_type", ""),
            "view_res": _view_match(o.get("view", "불확실"), gt.get("view", "")),
            "view_vlm": o.get("view"), "view_gt": gt.get("view"),
            "struct_res": _view_match(o.get("structure", "불확실"), gt.get("structure", "")),
            "struct_vlm": o.get("structure"), "struct_gt": gt.get("structure"),
            "fs_tp": tp, "fs_fp": fp, "fs_fn": fn_,
            "consistent": bool(o.get("consistent")),
            "confidence": o.get("confidence"),
        })
    return rows, _aggregate(rows)


def _acc(rows, key):
    c = sum(1 for r in rows if r.get(key) == "correct")
    w = sum(1 for r in rows if r.get(key) == "wrong")
    a = sum(1 for r in rows if r.get(key) == "abstain")
    tot = c + w  # 기권/skip 제외한 '판정한 것' 중 정확도
    return {"correct": c, "wrong": w, "abstain": a, "acc": (c / tot) if tot else None}


def _aggregate(rows):
    ok = [r for r in rows if "error" not in r]
    agg = {"n": len(rows), "scored": len(ok), "errors": len(rows) - len(ok)}
    if not ok:
        return agg
    agg["view"] = _acc(ok, "view_res")
    agg["structure"] = _acc(ok, "struct_res")
    tp = sum(r["fs_tp"] for r in ok); fp = sum(r["fs_fp"] for r in ok); fn = sum(r["fs_fn"] for r in ok)
    p, r_, f = _prf(tp, fp, fn)
    agg["foreshortening"] = {"P": p, "R": r_, "F1": f, "tp": tp, "fp": fp, "fn": fn}
    # 케이스별 분해
    by_case = {}
    for r in ok:
        by_case.setdefault(r["case_type"] or "(미지정)", []).append(r)
    agg["by_case"] = {c: {"n": len(rs), "view_acc": _acc(rs, "view_res")["acc"],
                          "struct_acc": _acc(rs, "struct_res")["acc"]}
                      for c, rs in sorted(by_case.items())}
    # 일관성 ↔ 정확성 (3단계 노출 게이트 근거)
    agg["consistency_vs_correct"] = {}
    for flag in (True, False):
        sub = [r for r in ok if r["consistent"] is flag]
        if sub:
            agg["consistency_vs_correct"][str(flag)] = {
                "n": len(sub), "view_acc": _acc(sub, "view_res")["acc"],
                "struct_acc": _acc(sub, "struct_res")["acc"]}
    return agg


def _print_report(rows, agg):
    print("=" * 64)
    for r in rows:
        if "error" in r:
            print(f"  {r['file']:28s}  ERROR: {r['error']}")
            continue
        v = {"correct": "✓", "wrong": "✗", "abstain": "·", "skip": "—"}
        print(f"  {r['file']:24s} [{r['case_type']:6s}] "
              f"view {v[r['view_res']]}({r['view_vlm']}/{r['view_gt']})  "
              f"struct {v[r['struct_res']]}({r['struct_vlm']}/{r['struct_gt']})  "
              f"fs tp{r['fs_tp']}/fp{r['fs_fp']}/fn{r['fs_fn']}  "
              f"{'일관' if r['consistent'] else '불일치'}")
    print("-" * 64)
    print(f"채점 {agg['scored']}/{agg['n']}  (에러 {agg['errors']})")
    if agg.get("view"):
        print(f"view 정확도     : {_fmt(agg['view']['acc'])}  (맞{agg['view']['correct']}/틀{agg['view']['wrong']}/기권{agg['view']['abstain']})")
        print(f"structure 정확도: {_fmt(agg['structure']['acc'])}  (맞{agg['structure']['correct']}/틀{agg['structure']['wrong']}/기권{agg['structure']['abstain']})")
        fsm = agg["foreshortening"]
        print(f"foreshortening : P={_fmt(fsm['P'])} R={_fmt(fsm['R'])} F1={_fmt(fsm['F1'])}  (tp{fsm['tp']}/fp{fsm['fp']}/fn{fsm['fn']})")
        print("케이스별:")
        for c, m in agg["by_case"].items():
            print(f"  {c:10s} n={m['n']:2d}  view={_fmt(m['view_acc'])} struct={_fmt(m['struct_acc'])}")
        print("일관성 ↔ 정확성 (노출 게이트 근거):")
        for flag, m in agg["consistency_vs_correct"].items():
            tag = "consistent=true " if flag == "True" else "consistent=false"
            print(f"  {tag}  n={m['n']:2d}  view={_fmt(m['view_acc'])} struct={_fmt(m['struct_acc'])}")


def _fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def _selftest():
    """키·이미지 없이 대조·집계 로직 검증(observe_hand 목)."""
    labels = {
        "a.jpg": {"case_type": "손등", "view": "손등", "structure": "입체", "foreshortening": ["중지", "약지"]},
        "b.jpg": {"case_type": "주먹", "view": "손등", "structure": "입체", "foreshortening": ["검지", "중지", "약지", "소지"]},
        "c.jpg": {"case_type": "만화체", "view": "손바닥", "structure": "평면", "foreshortening": []},
    }
    mock = {
        "a.jpg": {"view": "손등", "structure": "입체", "foreshortening": ["가운데", "약지"], "consistent": True, "confidence": "관찰"},
        "b.jpg": {"view": "손바닥", "structure": "입체", "foreshortening": ["검지", "중지"], "consistent": True, "confidence": "관찰"},
        "c.jpg": {"view": "불확실", "structure": "혼합", "foreshortening": ["엄지"], "consistent": False, "confidence": "낮음"},
    }

    def runner(path):
        return mock[os.path.basename(path)]
    # 이미지 존재 우회: 임시 빈 파일
    import tempfile
    d = tempfile.mkdtemp()
    for k in labels:
        open(os.path.join(d, k), "w").close()
    rows, agg = evaluate(d, labels, runner=runner)
    # a: view 맞(손등), struct 맞(입체), fs tp=2(중지·약지) fp0 fn0
    ra = next(r for r in rows if r["file"] == "a.jpg")
    assert ra["view_res"] == "correct" and ra["struct_res"] == "correct", ra
    assert (ra["fs_tp"], ra["fs_fp"], ra["fs_fn"]) == (2, 0, 0), ra
    # b: view 틀(손바닥≠손등), fs tp2(검지·중지) fn2(약지·소지)
    rb = next(r for r in rows if r["file"] == "b.jpg")
    assert rb["view_res"] == "wrong", rb
    assert (rb["fs_tp"], rb["fs_fp"], rb["fs_fn"]) == (2, 0, 2), rb
    # c: view 기권(불확실), struct 틀(혼합≠평면)
    rc = next(r for r in rows if r["file"] == "c.jpg")
    assert rc["view_res"] == "abstain" and rc["struct_res"] == "wrong", rc
    # 집계: view 판정 2건 중 1맞1틀 → 0.5
    assert abs(agg["view"]["acc"] - 0.5) < 1e-9, agg["view"]
    # 일관성↔정확성: consistent=true 2건(a맞,b틀)→0.5; false 1건(c기권)→판정0 n/a
    assert agg["consistency_vs_correct"]["True"]["view_acc"] == 0.5
    print("selftest OK — view/struct 대조, foreshortening tp/fp/fn, 기권 처리, 케이스·일관성 집계 정상")


def debug_call(folder):
    """no_observation 원인 표면화: 백엔드·자격 상태 + 첫 이미지에 _call 직접 호출해 실제 에러를 보인다.
    observe_hand 는 예외를 삼켜 None 만 주므로, 디버그는 저수준 _call 을 직접 때려 에러를 노출한다."""
    import ml.vision as V
    print(f"VLM_BACKEND    = {V._BACKEND!r}   (aistudio=API키 | vertex=GCP ADC)")
    if V._BACKEND == "vertex":
        print(f"GOOGLE_CLOUD_PROJECT  = {V._VX_PROJECT!r}")
        print(f"GOOGLE_CLOUD_LOCATION = {V._VX_LOCATION!r}")
        print(f"GOOGLE_APPLICATION_CREDENTIALS = {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')!r}")
        try:
            tok = V._vertex_token()
            print(f"ADC 토큰 발급 ✓ (길이 {len(tok)})")
        except Exception as e:
            print(f"ADC 토큰 발급 ✗ — {type(e).__name__}: {e}")
            print("  · ImportError → google-auth 미설치(requirements 추가 후 --build)")
            print("  · DefaultCredentialsError → GOOGLE_APPLICATION_CREDENTIALS(서비스계정 JSON) 미설정/미마운트")
    else:
        key = os.environ.get("GEMINI_API_KEY", "")
        print(f"GEMINI_API_KEY = 설정 {bool(key)}, 길이 {len(key)}   (자리표시자/빈값이면 실패)")
    print(f"HAND_VLM = {os.environ.get('HAND_VLM')!r}  (디버그는 게이트 무관 — _call 직접 호출)")
    print(f"모델     = {V._MODEL}")
    imgs = _images(folder)
    if not imgs:
        print(f"이미지 없음: {folder}")
        return
    path = imgs[0]
    print(f"테스트 이미지 = {os.path.basename(path)}")
    try:
        b64, mime = V._to_b64(path)
        raw = V._call(b64, mime, os.environ.get("GEMINI_API_KEY", ""))
        print(f"CALL 성공 ✓ — 응답 앞부분: {raw[:160]!r}")
    except Exception as e:
        print(f"CALL 실패 ✗ — {type(e).__name__}: {e}")
        print("  · 400/401/403 → 자격(키/권한)  · 429 → 레이트리밋/쿼터")
        print("  · Connection/Timeout/SSL → 엔드포인트 도달 못함(네트워크)")
        print("  · 그 외 → 모델명/응답 형식 확인")


def main(argv):
    if "--selftest" in argv:
        _selftest()
        return
    pos = [a for a in argv if not a.startswith("--")]
    if "--init" in argv:
        if not pos:
            print("사용: --init <폴더>")
            return
        init_template(pos[0])
        return
    if "--debug" in argv:
        if not pos:
            print("사용: --debug <폴더>  (-e GEMINI_API_KEY=.. 와 함께)")
            return
        debug_call(pos[0])
        return
    if not pos:
        print(__doc__)
        return
    folder = pos[0]
    lpath = None
    for i, a in enumerate(argv):
        if a == "--labels" and i + 1 < len(argv):
            lpath = argv[i + 1]
    lpath = lpath or os.path.join(folder, "labels.json")
    if not os.path.exists(lpath):
        print(f"라벨 파일 없음: {lpath}  (먼저 --init 로 템플릿 만들고 채우세요)")
        return
    with open(lpath, encoding="utf-8-sig") as f:   # utf-8-sig: 혹시 모를 BOM(파워셸 저장 등) 견딤
        labels = json.load(f)
    sleep = 0.0
    for i, a in enumerate(argv):
        if a == "--sleep" and i + 1 < len(argv):
            sleep = float(argv[i + 1])
    rows, agg = evaluate(folder, labels, sleep=sleep)
    _print_report(rows, agg)


if __name__ == "__main__":
    main(sys.argv[1:])
