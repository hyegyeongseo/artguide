"""smoke_security.py — 떠 있는 API 서버에 실제 요청을 보내 보안 배선이 동작하는지 확인.

test_main_wiring.py 가 '코드에 배선됐나'(정적)라면, 이건 '실제로 거절하나'(런타임)다.
서버를 띄운 뒤 실행:
    docker compose up -d
    python scripts/smoke_security.py                       # 기본 http://localhost:8000
    BASE=http://localhost:8000 python scripts/smoke_security.py

검사:
  1) /adopt 에 잘못된 event → 400
  2) /practice 에 잘못된 action → 400
  3) /image/<비-UUID> → 404 (또는 리다이렉트 아님)
  4) /ai-example/qc 라우트 존재(422 = 폼 누락이지 404 아님)
  5) /healthz → 200 (서버 살아있음)
실패해도 다른 검사는 계속한다. 종료코드 = 실패 개수.
"""
import os
import sys

try:
    import requests
except ImportError:
    print("requests 필요: pip install requests", file=sys.stderr)
    sys.exit(2)

BASE = os.environ.get("BASE", "http://localhost:8000").rstrip("/")
fails = 0


def check(name, cond, detail=""):
    global fails
    ok = bool(cond)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")
    if not ok:
        fails += 1


def main():
    print(f"대상: {BASE}\n")
    try:
        r = requests.get(f"{BASE}/healthz", timeout=5)
        check("healthz 200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("서버 연결", False, repr(e)[:80])
        print("\n서버가 안 떠 있는 것 같습니다. docker compose up -d 후 재실행.")
        sys.exit(1)

    # B-4: 잘못된 event
    r = requests.post(f"{BASE}/adopt", json={
        "guide_id": "g", "reference_id": "r", "persona": "pose",
        "source_type": "museum", "event": "HACK"}, timeout=5)
    check("/adopt 잘못된 event → 400", r.status_code == 400, f"status={r.status_code}")

    # B-4: 정상 event 는 통과(400 아님). DB 없으면 500 일 수 있으나 400 만 아니면 검증은 통과한 것.
    r = requests.post(f"{BASE}/adopt", json={
        "guide_id": "g", "reference_id": "r", "persona": "pose",
        "source_type": "museum", "event": "saved"}, timeout=5)
    check("/adopt 정상 event 는 400 아님", r.status_code != 400, f"status={r.status_code}")

    # B-4: 잘못된 action
    r = requests.post(f"{BASE}/practice", json={
        "user_id": "u", "sub_problem": "proportion", "action": "NOPE"}, timeout=5)
    check("/practice 잘못된 action → 400", r.status_code == 400, f"status={r.status_code}")

    # B-3: 비-UUID ref_id → 404 (리다이렉트/200 아님)
    r = requests.get(f"{BASE}/image/not-a-uuid", timeout=5, allow_redirects=False)
    check("/image 비-UUID → 404", r.status_code == 404, f"status={r.status_code}")

    # 라우터 마운트: /ai-example/qc 존재(폼 누락 422, 라우트 없음 404 아님)
    r = requests.post(f"{BASE}/ai-example/qc", timeout=5)
    check("/ai-example/qc 라우트 존재(404 아님)", r.status_code != 404, f"status={r.status_code}")

    print(f"\n실패 {fails}개." if fails else "\n전부 통과 ✅")
    sys.exit(fails)


if __name__ == "__main__":
    main()
