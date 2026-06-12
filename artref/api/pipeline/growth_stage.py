"""pipeline/growth_stage.py — '내부' 성장 단계 추정(커리큘럼 진입점·코칭 톤 조정용).

────────────────────────────────────────────────────────────────────────────
멘토링 반영:  "사용자 실력을 나누는 건 어렵고 중요하지 않다. 하지만 초보→중급으로 나아가는
              로드맵은 분명히 존재하며, 이를 *외부로 드러내지 않더라도 내부적으로* 갖고 있는
              것이 중요하다."  →  이 모듈은 그 '내부 로드맵 좌표'를 만든다.

★ 불변식(절대 위반 금지) ─ 이 stage 는 **내부 신호**다.
  • 사용자 응답 텍스트/블록/배지로 새어나가면 안 된다. 가드레일(safety/validate)이 막는
    평가어(초보·고수·점수·등급)와 같은 범주다. 여기서 만든 stage 는 *그 라벨이 아니라*
    커리큘럼 위 좌표(foundation→developing→refining)이며, 하는 일은 둘뿐이다:
       (a) 콜드스타트(이력 0)일 때 '어디서부터 같이 볼지' 진입 축을 그림에서 고른다.
       (b) 코칭 톤(얼마나 풀어서 설명할지)의 내부 힌트.
  • API 응답·스키마에 stage 문자열을 그대로 싣지 않는다(이 모듈을 호출하는 쪽 책임).

따라서 "실력을 판정"하지 않는다 — 커리큘럼의 *어느 지점에서 함께 보면 효과적인가*만 정한다.
LLM 없이 결정적. 이력이 없으면 그림 자체(측정된 약점)로만 진입점을 잡는다.
"""

# 내부 단계 id(노출 금지). 진척 비율·약점 분포로 가르는 '커리큘럼 좌표'일 뿐.
FOUNDATION = "foundation"     # 큰 구조부터 같이 보는 구간
DEVELOPING = "developing"     # 구조는 잡혀가고 디테일로 확장하는 구간
REFINING = "refining"         # 대부분 자리잡고 다듬는 구간


def estimate_stage(steady, total, trend="new", total_tries=0):
    """진척(자리잡은 축 수/전체)·추세로 내부 단계를 정한다. (stage, ratio) 반환.

    판정이 아니라 '구조 먼저' 사다리에서의 위치다. 자리잡은 축이 거의 없으면 foundation,
    절반 이상이면 refining. 추세가 개선 중이면 살짝 위로 본다(같은 비율이라도 상승세 가산).
    """
    total = max(int(total or 0), 1)
    steady = max(int(steady or 0), 0)
    ratio = min(steady / total, 1.0)
    bump = 0.05 if trend == "decreasing" else 0.0   # 개선 추세 소폭 가산(경계 근처만 영향)
    score = ratio + bump
    if score >= 0.5:
        return REFINING, ratio
    if score >= 0.2 or total_tries >= 2:
        return DEVELOPING, ratio
    return FOUNDATION, ratio


def cold_start_focus(flagged, curriculum):
    """이력 0(콜드스타트)일 때 '이 그림에서 같이 볼 첫 축'을 고른다.

    flagged = 이번 업로드에서 **측정으로** 떠오른 약점 sub_problem 들.
    커리큘럼(구조 먼저) 순서에서 가장 앞쪽에 떠오른 약점을 진입점으로 삼는다 →
    구조가 탄탄한 그림(앞쪽 약점 없음)은 자연히 더 뒤 단계에서 시작하게 된다(개인화).
    측정 약점이 하나도 없으면 None(호출부가 커리큘럼 첫 단계로 폴백).
    """
    fl = set(flagged or ())
    for sp in curriculum:
        if sp in fl:
            return sp
    return None


def is_cold(growth):
    """growth 가 콜드스타트(연습/노출 이력이 사실상 없음)인지. growth_context 가 넣은 'cold' 우선."""
    if not growth:
        return True
    if "cold" in growth:
        return bool(growth["cold"])
    # 폴백 추정: 자리잡은 것도 자주 막히는 것도 없으면 콜드로 본다.
    return not growth.get("steady") and not growth.get("recurring")


def apply_cold_start(growth, measured_subproblems, curriculum, why_fn=None):
    """콜드스타트면 진입 집중 축을 '그림에서 측정된 약점'으로 교정한다(제자리 수정 후 growth 반환).

    이력이 쌓이면(is_cold=False) 아무것도 바꾸지 않는다 — 그때부턴 로드맵 이력이 더 정확하다.
    measured_subproblems = 이번 dx 에서 measured=True 로 뜬 축들(가설형 약한 추정은 제외).
    why_fn(focus, next_goal) 를 주면 'why' 문구도 새 진입점에 맞춰 갱신한다(노출용, 평가어 아님).
    """
    if not growth or not is_cold(growth):
        return growth
    cf = cold_start_focus(measured_subproblems, curriculum)
    if not cf:
        return growth
    growth["current_focus"] = cf
    idx = curriculum.index(cf) if cf in curriculum else -1
    nxt = curriculum[idx + 1] if 0 <= idx < len(curriculum) - 1 else growth.get("next_goal")
    growth["next_goal"] = nxt
    if why_fn:
        try:
            growth["why"] = why_fn(cf, nxt)
        except Exception:
            pass
    return growth
