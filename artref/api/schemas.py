from pydantic import BaseModel, Field
from typing import Optional, Literal

class Action(BaseModel):
    type: Literal["COACH", "REDIRECT_GENERATE", "CLARIFY", "CHITCHAT", "ANCHOR_REF"]
    args: dict = {}

class GuideBlock(BaseModel):
    sub_problem: str
    observation: str
    effect: str = ""
    direction: str = ""
    reference_ids: list[str] = []
    confidence: float = Field(ge=0, le=1)

class GuideResponse(BaseModel):
    mode: Literal["coach", "redirect", "clarify", "refused"]
    guide_id: Optional[str] = None
    primary_focus: Optional[str] = None
    degraded: bool = False
    blocks: list[GuideBlock] = []
    synthesis: Optional[str] = None
    one_thing: Optional[str] = None
    message: Optional[str] = None
