"""_auth 회귀 테스트 — 미설정 시 무인증, 설정 시 헤더 키 요구.

실행: artref/api 에서  python -m tests.test_auth
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _auth import is_authorized, extract_key, _keys


def t_no_key_setting_is_open():
    # API_KEY 미설정(빈 값) → 항상 허용(로컬/WoZ/테스트 그대로).
    assert is_authorized({}, "") is True
    assert is_authorized({"x-api-key": "anything"}, "") is True


def t_x_api_key_header_match():
    assert is_authorized({"x-api-key": "secret1"}, "secret1") is True


def t_bearer_token_match():
    assert is_authorized({"authorization": "Bearer secret1"}, "secret1") is True


def t_wrong_key_rejected():
    assert is_authorized({"x-api-key": "nope"}, "secret1") is False


def t_missing_key_when_required_rejected():
    assert is_authorized({}, "secret1") is False


def t_multiple_keys_supported():
    assert is_authorized({"x-api-key": "k2"}, "k1,k2,k3") is True
    assert is_authorized({"x-api-key": "k9"}, "k1,k2,k3") is False


def t_extract_key_forms():
    assert extract_key({"x-api-key": "  abc "}) == "abc"
    assert extract_key({"authorization": "Bearer xyz"}) == "xyz"
    assert extract_key({"authorization": "Basic zzz"}) is None
    assert extract_key({}) is None


def t_keys_parsing():
    assert _keys("a, b ,c") == {"a", "b", "c"}
    assert _keys("") == set()
    assert _keys(None) == set()


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 무인증기본·헤더키·Bearer·다중키")


if __name__ == "__main__":
    run()
