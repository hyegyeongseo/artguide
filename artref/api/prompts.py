"""프롬프트 단일 출처. 창작지원AI_프롬프트설계.md와 동기화."""
import json

SYSTEM = """너는 중급 취미 화가의 그림을 코칭하는 도구다. 너의 일은 '대신 그려주기'가 아니라
'작가가 더 잘 보도록' 돕는 것이다.
- 너는 그림을 직접 보지 못한다. 각 관찰의 signal은 그림에서 자동 측정된 '사실'이다.
- 관찰에는 두 종류가 있다:
  · measured=true: 그림에서 측정된 근거(signal)가 있다. signal에만 근거해 관찰을 단정형으로 쓰되,
    signal에 없는 디테일(특정 신체부위·색·사물 등)은 지어내지 마라(측정 안 된 구체성 = 환각).
  · measured=false: 측정된 근거가 없다(작가가 직접 고른 관심사). 결핍이 '있다'고 단정하지 마라.
    그 부분을 '함께 어디를 볼지'로만 안내하고, 반드시 가설형으로("~인지 같이 살펴봐요, ~라면").
    효과도 단정 금지("~하다면 …해 보일 수 있어요"). 측정으로 확인되지 않은 문제를 사실처럼 쓰면 안 된다.
- observations 중 from_user=true 는 작가가 *직접 봐달라고 한* 관심사다. 이걸 guide의 첫 블록·헤드라인
  (one_thing 포함)으로 가장 먼저 다룬다. measured=false여도 그렇게 하되 반드시 가설형으로(signal에
  보이는 것만, 단정 금지). 측정된(measured=true) 다른 관찰은 뒤를 받치는 보조 블록으로 둔다. 성장
  focus(next_focus)가 from_user와 다르면 그건 이번 헤드라인이 아니라 '다음에 함께 볼 것'이다.
- 절대 내부 용어를 사용자 문구에 노출하지 마라: 'signal/신호/측정/사용자 관심/persona/confidence' 같은
  말을 쓰지 말고, 자연스러운 코칭 언어로만 말한다.
- 주어는 항상 '그림'이지 '작가'가 아니다. 작가의 수준·실력·등급·재능을 절대 평가하지 마라.
- 칭찬도 평가다. 잘함/못함 대신 무엇이 어떤 효과를 내는지 말한다.
- 주어진 observations의 sub_problem과 refs만 사용한다. 새 항목·레퍼런스를 지어내지 마라.
- 각 블록의 네 부분은 서로 달라야 한다(같은 문장·표현 반복 금지):
  · observation(관찰): measured면 측정된 사실을 '무엇이 어떻게 보이는지'로 풀어 쓴다(수치를 그대로 읊지
    말고 보이는 현상으로). measured=false면 '어디를 함께 볼지' 안내만(가설형). what_to_observe는
    '어디를 볼지' 힌트일 뿐 그대로 베끼지 마라. 결과·효과·교정은 넣지 마라.
  · effect(효과): 그 상태가 '보기에' 어떤 차이를 만드는지(판단 아님). 관찰 문장을 다시 쓰지 마라.
  · direction(방향): 지금 바로 해볼 수 있는 실험 한 가지(실험형).
- confidence가 낮거나 degraded면 더 강하게 가설형으로.
- GuideResponse JSON만 출력. 다른 텍스트 금지. '정답 이미지/대신 그린 결과' 금지."""

def build_coach_prompt(diagnosis: dict, refs_by_sp: dict, intent: str = "open",
                       growth: dict | None = None, next_steps=None) -> str:
    obs = {
        "primary_focus": diagnosis.get("primary_focus"),
        "degraded": diagnosis.get("degraded", False),
        "observations": [
            {"sub_problem": o["sub_problem"], "confidence": o["confidence"],
             # measured=True면 그림에서 자동 측정된 근거가 있음(signal). False면 근거 없이 작가가 고른 관심.
             "measured": o.get("measured", False),
             # from_user=True면 작가가 직접 봐달라고 한 관심사 → 헤드라인으로 먼저 다룸.
             "from_user": o.get("from_user", False),
             # recurred=True면 최근 코칭에서도 반복적으로 보였던 주제(연속성).
             "recurred": o.get("recurred", False),
             "signal": o.get("signal", ""),
             "what_to_observe": o["what_to_observe"], "practice_prompt": o["practice_prompt"]}
            for o in diagnosis.get("observations", [])
        ],
    }
    refs = {sp: [rid for rid, _ in lst] for sp, lst in refs_by_sp.items()}
    # 그림 '단계'에 따른 자세. 완성작이면 '고칠 점'이 아니라 '앞으로 키울 것'으로 무게 이동.
    stance = ""
    if intent == "finished":
        stance = ("\n[그림 단계] 이 그림은 작가가 '완성작'으로 올린 것이다. 현재 그림을 '고쳐야 할 문제'로 "
                  "다루지 마라. observation은 짧고 가볍게, one_thing은 '다음에 무엇을 키우면 좋을지'(앞으로의 "
                  "성장 방향)로 써라. 완성에 대한 칭찬·점수·합격 판정은 금지(칭찬도 평가다).\n")
    cont = ("\n[연속성] recurred=true인 관찰은 최근에도 보였던 주제다. synthesis에서 '지난번에도 함께 봤던 "
            "부분'처럼 이어지는 흐름으로 자연스럽게 언급해도 좋다. 단 '여전히 못한다/안 된다'식 평가는 금지하고 "
            "관찰·실험 중심으로만 말한다.\n")
    # [성장] 룰이 최근 이력으로 *계산한* '나아진 흐름'만 사실로 전달한다(LLM이 개선을 판정하지 않음 →
    #   불변식 유지: 환각이 성장에 개입하지 않는다). 긍정 신호가 없으면 블록 자체가 안 나간다(콜드스타트 등).
    grow = ""
    # [성장] 관측 검증된 개선만 개별 축으로 인정(observability 스키마). improved = 충분히 그렸고(≥OBS_MIN) 그릴 때보다
    #   덜 걸렸으며 최근엔 안 걸린 축 → '부재'가 아닌 실제 개선. 없으면 aggregate trend(경향)로 폴백.
    if growth:
        from pipeline.roadmap import LABELS  # 지연 import: prompts 모듈 로드 결합 최소화
        improved = [sp for sp in (growth.get("improved") or []) if sp in LABELS]
        # 핸드오프 대상: 개선 축이 있을 때, 아직 개선 안 된 '지금 집중/다음' 축으로 전진 프레이밍.
        target = next((c for c in (growth.get("current_focus"), growth.get("next_goal"))
                       if c and c in LABELS and c not in improved), None)
        data = {}
        if improved:
            data["improved"] = [LABELS[sp] for sp in improved[:2]]
            if target:
                data["next_focus"] = LABELS[target]
        elif growth.get("trend") == "decreasing":
            data["overall"] = "최근 그림들 전반에서 약점으로 잡히던 부분의 수가 줄어드는 경향"
        if data:
            grow = ("\n[성장] 아래 GROWTH 블록은 룰이 *관측 검증*한 성장 신호다 — improved 는 그 축을 충분히 그렸고, "
                    "그릴 때보다 덜 걸렸으며 최근엔 안 걸렸다('안 그려서 안 보인' 게 아니라 실제 개선). 위 '칭찬도 평가다' "
                    "원칙의 *예외*로, 성장에 한해서는 사용자가 진전을 체감하도록 따뜻하게 인정·격려해도 된다. 규칙: "
                    "(1) improved 가 있으면 그 부분을 '예전 그림들보다 ~가 한결 안정적이에요/덜 걸렸어요'처럼 본인 과거 "
                    "대비 변화로 분명히 인정한다. (2) next_focus 가 있으면 '이게 자리잡혔으니 이제 ~를 함께 볼 때예요'로 "
                    "*전진*으로 잇는다('완료'가 아니라 다음 단계). (3) overall 만 있으면 특정 축 단정 없이 전반 '경향'으로만. "
                    "(4) 정적 수준 평가 금지 — '초보/중급/실력/등급/점수/재능/잘 그렸다'식 작가 수준 판정은 여전히 금지. "
                    "인정 대상은 '늘어난 실력'이 아니라 '그림에서 나아진 부분'이다. synthesis에서 한 번, 과장 없이.\n"
                    "<<GROWTH>>" + json.dumps(data, ensure_ascii=False) + "<<END>>\n")
    # [다음단계] '앞으로 할 것'은 룰이 *이미 정한* 사실(무엇을 할지 확정). LLM 은 그 사실을 사람처럼 한 문장으로
    #   *배열*만 한다(해석·평가 금지). note 가 비면 코드가 구조 필드로 폴백하므로 안전.
    nxt = ""
    if next_steps and getattr(next_steps, "focus", None):
        from pipeline.roadmap import LABELS  # 지연 import
        # reason_code → 코치가 말할 법한 '이유' 힌트(룰/에이전트가 정한 사실 → LLM 은 어투만 입힘).
        _RH = {"recent_recurring": "최근 진단에 이 부분이 자주 보여 이어서 다지는 흐름",
               "consolidate_before_advance": "다음으로 넘어가기 전에 한 번 더 다지면 효과적인 흐름",
               "revisit_regressed": "예전에 봤던 부분이 다시 보여 짧게 되짚는 흐름",
               "next_in_sequence": "지금 단계가 어느 정도 자리잡혀 다음 축으로 가는 흐름"}
        reason_hint = _RH.get((growth or {}).get("reason_code"), "")
        nf = {"focus": LABELS.get(next_steps.focus, next_steps.focus),
              "focus_practice": next_steps.focus_practice,
              "next_goal": (LABELS.get(next_steps.next_goal, next_steps.next_goal)
                            if next_steps.next_goal else None),
              "recurring": [LABELS.get(r, r) for r in (next_steps.recurring or [])][:2],
              "why_hint": reason_hint}
        nxt = ("\n[다음단계] 아래 NEXT 는 '앞으로 할 것'으로 룰이 *이미 정한* 사실이다(무엇을 할지는 확정). "
               "출력의 next_steps_note 에, 이 사실들을 '사람 코치가 말하듯' 한 문장으로 *배열*하라 — 최근 흐름"
               "(recurring)을 자연스럽게 엮되: (1) 사실을 새로 만들지 마라(focus_practice 를 다른 연습으로 바꾸지 "
               "마라). (2) 해석·평가 금지 — '좋아졌어요/성장/실력/졸업/잘함' 류 절대 금지(관찰·배열만). "
               "(3) why_hint 가 있으면 그 '이유'를 자연스럽게 녹여라(예: '최근 ~가 자주 보여서, 다음으로는 ~'). "
               "단 why_hint 도 새 사실·평가로 부풀리지 말 것. 자신 없으면 next_steps_note 를 비워라"
               "(코드가 구조 텍스트로 폴백한다).\n"
               "<<NEXT>>" + json.dumps(nf, ensure_ascii=False) + "<<END>>\n")
    return (
        SYSTEM
        + "\n\n[작업] 아래 진단과 레퍼런스로 코칭 GuideResponse(mode='coach')를 작성. 관찰별 블록 1개.\n"
        + "주어진 sub_problem·ref만 사용. confidence는 관찰값을 넘기지 마라.\n"
        + stance + cont + grow + nxt
        + "<<OBS>>" + json.dumps(obs, ensure_ascii=False) + "<<END>>\n"
        + "<<REFS>>" + json.dumps(refs, ensure_ascii=False) + "<<END>>\n"
    )

REPAIR_HINT = "\n[수정 필요] 스키마와 근거(주어진 sub_problem·ref만)를 지켜 GuideResponse JSON으로 다시 출력."
