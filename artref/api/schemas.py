from pydantic import BaseModel, Field
from typing import Optional, Literal

class Action(BaseModel):
    type: Literal["COACH", "REDIRECT_GENERATE", "CLARIFY", "CHITCHAT", "ANCHOR_REF"]
    args: dict = {}

class GuideAsset(BaseModel):
    """'설명 자료 슬롯' — 제안을 *설명*하는 자료 한 개(참고작 슬롯과 별개). 코드가 후보 중에서 결정적으로 고름.

    type 으로 무엇을 보고 있는지 알린다: svg(결정적 도해) / backbone_3d(기하 참고) / ai_example(AI 일러스트).
    ref_id 가 'floor:<축>'이면 그 축의 항상-가능한 svg 도식 바닥이다(적재 자료가 없을 때의 폴백).
    """
    type: Literal["svg", "ai_example", "backbone_3d"]
    ref_id: str
    label: str                       # 사용자 노출 배지: 도식 / AI 예시 / 3D 참고
    caption: str = ""

class GuideBlock(BaseModel):
    sub_problem: str
    observation: str
    effect: str = ""
    direction: str = ""
    reference_ids: list[str] = []
    confidence: float = Field(ge=0, le=1)
    guide_asset: Optional[GuideAsset] = None   # 코드가 채움(가드레일 뒤, 결정적) — 제안 설명용 자료 1개

class NextSteps(BaseModel):
    """'앞으로 할 것' — 로드맵에서 결정적으로 채우는 블록(LLM 아님). 완성작/연속성 응답의 근거."""
    focus: Optional[str] = None             # 지금 집중할 sub_problem
    focus_practice: Optional[str] = None    # 그 축의 연습 한 가지
    next_goal: Optional[str] = None         # 다음 목표 sub_problem
    next_goal_practice: Optional[str] = None
    recurring: list[str] = []               # 자주 막히는 부분
    why: Optional[str] = None               # 왜 지금 이걸/다음 저걸(구조 먼저 원칙)
    focus_asset: Optional["GuideAsset"] = None   # 지금 집중 축의 설명 자료(코드가 결정적으로 채움)

class GuideResponse(BaseModel):
    mode: Literal["coach", "redirect", "clarify", "refused"]
    guide_id: Optional[str] = None
    primary_focus: Optional[str] = None
    degraded: bool = False
    blocks: list[GuideBlock] = []
    synthesis: Optional[str] = None
    one_thing: Optional[str] = None
    message: Optional[str] = None
    next_steps: Optional[NextSteps] = None   # 코드가 채움(완성작/이력 있을 때) — 가드레일 뒤 결정적 설정
