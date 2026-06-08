def screen_upload(pil) -> dict:
    """입력 이미지 안전 스크리닝. 성적/폭력/미성년 관련 차단.
    베타: 외부 모더레이션 API/분류기 훅을 연결. 미연결 시 보수적으로 진행.
    최소선: analyzable 게이트로 비-작품 거절, 인물 신원 식별 안 함, 인물 이미지 생성 안 함."""
    # TODO: provider 연결
    return {"allow": True, "reason": None}
