"""safety/moderation.py — 업로드 안전 스크리닝(이제 실제 동작; 기존 no-op 스텁 대체).

기존 시그니처 그대로: screen_upload(pil) -> {"allow": bool, "reason": str|None}.
main.py 의 `if not screen_upload(pil)["allow"]: ... refused` 가 수정 없이 동작한다.

실제 판정은 safety/screen.screen() 에 위임한다(대조 CLIP baseline + 외부 provider 훅,
fail-open/closed 설정 가능). 한계·운영 권장은 screen.py 의 docstring 참고.
"""
from safety.screen import screen


def screen_upload(pil) -> dict:
    v = screen(pil)
    return {"allow": bool(v.get("allow", True)), "reason": v.get("reason")}
