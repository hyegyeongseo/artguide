"""seed_museum 드라이런 테스트 — 인프라/인터넷 없이 시드 *로직*을 검증.

실제 네트워크(Met)·CLIP·Qdrant·MySQL·MinIO 없이:
- requests를 Met 응답 형태로 모의
- normalize/ingest를 스텁으로 교체(호출 기록)
실제 seed_museum.py를 import해서 그 제어 흐름을 검증한다:
  ① CC0(isPublicDomain) + primaryImage 있는 것만 적재  ② persona 태그 정확
  ③ object 조회 실패 시 continue(크래시 X)  ④ search 파라미터 hasImages='true'(소문자)

실행:  python scripts/test_seed_dryrun.py    (artref 루트에서)
"""
import sys, types, io

# ── 무거운 의존성(ingest=CLIP/Qdrant/MySQL/MinIO, normalize=PIL/heif) 스텁 ──
sys.path.insert(0, "api")

INGEST_CALLS = []           # (pil, kwargs) 기록
SEARCH_PARAMS = []          # /search에 넘어간 params 기록

_fake_ingest = types.ModuleType("pipeline.ingest")
def _ingest(pil, **kw):
    INGEST_CALLS.append((pil, kw))
    return "ref_fake"
_fake_ingest.ingest = _ingest
sys.modules["pipeline.ingest"] = _fake_ingest

_fake_norm = types.ModuleType("ml.normalize")
def _normalize(fp):         # BytesIO(b"IMG<oid>") → b"IMG<oid>"
    return fp.getvalue()
_fake_norm.normalize = _normalize
sys.modules["ml.normalize"] = _fake_norm

# ── Met 응답 모의 데이터 ──────────────────────────────────────────────
#  101/104/105: CC0 + 이미지(적재 대상) · 102/106: 비-CC0(skip) · 103: 이미지 없음(skip)
#  107: object 조회가 예외(→ continue 검증)
OBJECTS = {
    101: {"objectID": 101, "isPublicDomain": True,  "primaryImage": "https://img/101.jpg",
          "artistDisplayName": "Artist A", "department": "Drawings", "title": "T101"},
    102: {"objectID": 102, "isPublicDomain": False, "primaryImage": "https://img/102.jpg",
          "title": "T102"},
    103: {"objectID": 103, "isPublicDomain": True,  "primaryImage": "",
          "title": "T103"},
    104: {"objectID": 104, "isPublicDomain": True,  "primaryImage": "https://img/104.jpg",
          "artistDisplayName": "Artist B", "department": "Paintings", "title": "T104"},
    105: {"objectID": 105, "isPublicDomain": True,  "primaryImage": "https://img/105.jpg",
          "artistDisplayName": None, "department": "European", "title": "T105"},
    106: {"objectID": 106, "isPublicDomain": False, "primaryImage": "https://img/106.jpg",
          "title": "T106"},
    107: "RAISE",
}
SEARCH_IDS = [101, 102, 103, 104, 105, 106, 107]
VALID_IDS = {101, 104, 105}     # CC0 + 이미지


class _Resp:
    def __init__(self, payload=None, content=None):
        self._payload, self.content = payload, content
    def json(self):
        return self._payload


class _FakeRequests:
    def get(self, url, params=None, timeout=None):
        if "/search" in url:
            SEARCH_PARAMS.append(params or {})
            return _Resp(payload={"total": len(SEARCH_IDS), "objectIDs": list(SEARCH_IDS)})
        if "/objects/" in url:
            oid = int(url.rstrip("/").split("/")[-1])
            o = OBJECTS.get(oid)
            if o == "RAISE":
                raise RuntimeError("simulated object fetch failure")
            return _Resp(payload=o or {})
        if url.startswith("https://img/"):     # primaryImage 다운로드
            oid = url.split("/")[-1].split(".")[0]
            return _Resp(content=f"IMG{oid}".encode())
        raise AssertionError("unexpected URL: " + url)


# ── seed_museum import 후 의존성 주입 ─────────────────────────────────
import seed_museum  # noqa: E402  (위 스텁이 sys.modules에 먼저 들어가야 함)
seed_museum.requests = _FakeRequests()
seed_museum.time = types.SimpleNamespace(sleep=lambda *_: None)   # 레이트리밋 대기 제거


def _reset():
    INGEST_CALLS.clear(); SEARCH_PARAMS.clear()


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    return cond


def main():
    ok = True

    # ── T1: seed_persona("light") ── 2 쿼리 × 유효 3 = 6 적재 ──
    _reset()
    n = seed_museum.seed_persona("light", per_query=5)
    ok &= check(f"T1 적재 수 == 6 (실제 {n})", n == 6 and len(INGEST_CALLS) == 6)
    personas_all = [kw["personas"] for _, kw in INGEST_CALLS]
    ok &= check("T1 persona 태그 == ['light','mood']",
                all(p == ["light", "mood"] for p in personas_all))
    pils = {pil for pil, _ in INGEST_CALLS}
    ok &= check("T1 적재된 것은 CC0+이미지(101/104/105)뿐, 102/103/106 제외",
                pils == {b"IMG101", b"IMG104", b"IMG105"})
    meta_ok = all(kw["source_type"] == "museum" and kw["license"] == "CC0"
                  and kw["commercial_ok"] is True for _, kw in INGEST_CALLS)
    ok &= check("T1 메타(source_type=museum, license=CC0, commercial_ok=True)", meta_ok)

    # ── T2: hasImages 파라미터가 소문자 'true' ──
    ok &= check("T2 search params hasImages == 'true' (소문자)",
                all(p.get("hasImages") == "true" for p in SEARCH_PARAMS) and len(SEARCH_PARAMS) == 2)

    # ── T3: object 조회 예외(107)에도 크래시 없이 계속 ──
    ok &= check("T3 object 조회 실패(107) 흡수하고 정상 종료", n == 6)

    # ── T4: per_query 캡 동작 (유효 후보가 많을 때 limit에서 멈춤) ──
    _reset()
    big_valid = {i: {"objectID": i, "isPublicDomain": True,
                     "primaryImage": f"https://img/{i}.jpg", "title": f"T{i}"}
                 for i in range(200, 220)}
    OBJECTS.update(big_valid)
    globals_ids = list(range(200, 220))
    orig_search = SEARCH_IDS[:]
    SEARCH_IDS[:] = globals_ids
    n2 = seed_museum.seed_persona("pose", per_query=3)   # 2 쿼리 × 3 = 6
    ok &= check(f"T4 per_query=3 → 쿼리당 3에서 멈춤(2쿼리=6, 실제 {n2})", n2 == 6)
    SEARCH_IDS[:] = orig_search
    for i in big_valid:
        OBJECTS.pop(i, None)

    # ── T5: seed_all() 전 카테고리 (6 persona × 2 쿼리 × 유효 3 = 36) ──
    _reset()
    total = seed_museum.seed_all(per_query=5)
    ok &= check(f"T5 seed_all 총 적재 == 36 (실제 {total})", total == 36)
    cats = {tuple(kw["personas"]) for _, kw in INGEST_CALLS}
    ok &= check("T5 6개 카테고리 모두 등장",
                len(cats) == 6)

    print("\n" + ("ALL PASS ✅" if ok else "SOME FAILED ❌"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
