"""_ratelimit.py — 가벼운 요청 레이트리밋(남용·비용폭주 차단).

왜 필요한가: /guide·/analyze 는 LLM·CLIP·포즈 추출을 돌려 *호출당 비용*이 크다. 인증 없이
공개돼 있으면 한 클라이언트가 비용을 무한정 태우거나 /adopt 로 랭커를 오염시킬 수 있다.

설계 원칙(로컬 개발·테스트를 막지 않는다):
  • env RATE_LIMIT 가 비어 있으면 **완전히 비활성**(통과). 기본 동작은 그대로.
  • RATE_LIMIT="60/minute" 처럼 'N/기간'으로 설정하면 키별 한도가 켜진다.
  • REDIS_URL 이 있으면 Redis 고정창(분산 환경에서 정확), 없으면 in-process 토큰버킷(단일 인스턴스).
  키는 호출자(api-key 또는 client IP). main.py 의 미들웨어가 이 모듈을 호출한다.

이 모듈은 무거운 의존이 없다(redis 는 있을 때만 lazy import) → 단위 테스트가 쉽다.
"""
import time
import threading

_PERIODS = {"second": 1, "sec": 1, "s": 1,
            "minute": 60, "min": 60, "m": 60,
            "hour": 3600, "h": 3600, "day": 86400, "d": 86400}


def parse_rate(spec):
    """'60/minute' → (60, 60). 비었거나 형식이 틀리면 None(=비활성). 안전 기본값."""
    if not spec:
        return None
    try:
        n, _, period = spec.strip().partition("/")
        n = int(n)
        secs = _PERIODS[period.strip().lower()]
        if n <= 0:
            return None
        return (n, secs)
    except Exception:
        return None


class _LocalBucket:
    """단일 프로세스용 토큰버킷. 키별 (tokens, last_refill). 스레드 안전(락)."""

    def __init__(self, limit, window):
        self.limit = float(limit)
        self.rate = float(limit) / float(window)   # 초당 충전량
        self.window = window
        self._state = {}                            # key -> [tokens, last_ts]
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (self.limit, now))
            tokens = min(self.limit, tokens + (now - last) * self.rate)
            if tokens >= 1.0:
                self._state[key] = (tokens - 1.0, now)
                return True, 0
            # 다음 토큰까지 남은 시간(초)
            retry = int((1.0 - tokens) / self.rate) + 1
            self._state[key] = (tokens, now)
            return False, retry


class _RedisWindow:
    """REDIS_URL 있을 때: 고정창 카운터(INCR + EXPIRE). 여러 인스턴스에서 공유된 한도."""

    def __init__(self, client, limit, window):
        self.r = client
        self.limit = limit
        self.window = window

    def allow(self, key):
        bucket = int(time.time()) // self.window
        rk = f"rl:{key}:{bucket}"
        try:
            n = self.r.incr(rk)
            if n == 1:
                self.r.expire(rk, self.window)
            if n <= self.limit:
                return True, 0
            return False, self.window
        except Exception:
            # Redis 장애 시 *열어준다*(가용성 우선; 레이트리밋은 best-effort 보호막).
            return True, 0


class Limiter:
    """RATE_LIMIT(+선택 REDIS_URL)로 만든 레이트리밋. 비활성이면 항상 통과."""

    def __init__(self, rate_spec="", redis_url=""):
        parsed = parse_rate(rate_spec)
        self.enabled = parsed is not None
        if not self.enabled:
            self._backend = None
            return
        limit, window = parsed
        self.limit, self.window = limit, window
        client = _maybe_redis(redis_url)
        self._backend = _RedisWindow(client, limit, window) if client else _LocalBucket(limit, window)

    def allow(self, key):
        """(allowed: bool, retry_after_seconds: int). 비활성이면 (True, 0)."""
        if not self.enabled:
            return True, 0
        return self._backend.allow(key or "anon")


def _maybe_redis(redis_url):
    if not redis_url:
        return None
    try:
        import redis  # lazy: 설치/설정됐을 때만
        c = redis.Redis.from_url(redis_url, socket_connect_timeout=1)
        c.ping()
        return c
    except Exception as e:
        print(f"[ratelimit] Redis 연결 실패 → in-process 폴백: {type(e).__name__}: {e}")
        return None
