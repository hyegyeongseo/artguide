"""_auth.py — 선택적 API 키 인증.

설계: env API_KEY 가 **비어 있으면 무인증**(로컬 개발·WoZ·테스트는 그대로 동작).
API_KEY 가 설정되면 보호 라우트는 헤더로 키를 요구한다.
  허용 헤더:  X-API-Key: <key>   또는   Authorization: Bearer <key>
여러 키(키 회전·클라이언트 분리)를 콤마로 줄 수 있다: API_KEY="k1,k2".

main.py 의 미들웨어가 require_key()/extract_key() 를 호출한다. 순수 함수라 테스트가 쉽다.
"""


def _keys(api_key_setting):
    """콤마 구분 키 목록 → set. 비면 빈 set(=인증 비활성)."""
    return {k.strip() for k in (api_key_setting or "").split(",") if k.strip()}


def extract_key(headers):
    """요청 헤더에서 제시된 키를 뽑는다(없으면 None). headers 는 대소문자 무시 매핑."""
    def _get(name):
        try:
            return headers.get(name)
        except Exception:
            return None
    k = _get("x-api-key") or _get("X-API-Key")
    if k:
        return k.strip()
    auth = _get("authorization") or _get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def is_authorized(headers, api_key_setting):
    """인증 비활성(키 미설정)이면 항상 True. 활성이면 제시 키가 허용 집합에 있어야 True."""
    allowed = _keys(api_key_setting)
    if not allowed:
        return True                       # 무인증 모드(로컬/테스트)
    return extract_key(headers) in allowed
