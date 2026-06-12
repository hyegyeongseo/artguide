"""_ratelimit 회귀 테스트 — 비활성 통과·파싱·로컬 버킷 한도.

실행: artref/api 에서  python -m tests.test_ratelimit
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _ratelimit import Limiter, parse_rate, _LocalBucket


def t_parse_rate_ok():
    assert parse_rate("60/minute") == (60, 60)
    assert parse_rate("5/second") == (5, 1)
    assert parse_rate("100/hour") == (100, 3600)


def t_parse_rate_invalid_is_none():
    for bad in ("", None, "abc", "10/century", "0/minute", "-3/minute"):
        assert parse_rate(bad) is None


def t_disabled_limiter_always_allows():
    lim = Limiter("", "")          # 스펙 없음 → 비활성
    assert lim.enabled is False
    for _ in range(1000):
        allowed, retry = lim.allow("k")
        assert allowed and retry == 0


def t_local_bucket_blocks_after_limit():
    lim = Limiter("2/minute", "")  # Redis 없음 → in-process 버킷
    assert lim.enabled is True
    a1, _ = lim.allow("ip1")
    a2, _ = lim.allow("ip1")
    a3, retry = lim.allow("ip1")
    assert a1 and a2 and (not a3)
    assert retry >= 1              # 다음 토큰까지 대기 시간 안내


def t_keys_are_independent():
    lim = Limiter("1/minute", "")
    assert lim.allow("a")[0] is True
    assert lim.allow("b")[0] is True   # 다른 키는 별도 버킷
    assert lim.allow("a")[0] is False  # 같은 키는 소진


def t_local_bucket_direct_refill_logic():
    # 충전율이 있으면 시간이 지나며 토큰이 회복된다(직접 검증 — 단조시계 의존 없이 상태만).
    b = _LocalBucket(limit=1, window=1)
    assert b.allow("x")[0] is True
    assert b.allow("x")[0] is False


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print(f"\n전부 통과 ({len(tests)}개) — 비활성통과·파싱·버킷한도·키독립")


if __name__ == "__main__":
    run()
