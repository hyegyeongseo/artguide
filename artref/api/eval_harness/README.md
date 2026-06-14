# eval_harness — 명암 축 측정기 (baseline ↔ 마스크 비교)

"감으로 튜닝"을 끝내는 자(ruler). 기존 pipeline은 손대지 않고 분석기를 블랙박스로 채점.

## 쓰는 법
artref/api 에서 (컨테이너):
    docker compose exec -w /repo/api api python -m eval_harness.run_value /repo/samples/clean

- 폴더엔 **명도폭 넓은 깨끗한 그림**(png/jpg). 이들이 음성 = false positive 기준.
- 하니스가 '명도 폭 좁음' 결함을 severity별로 주입(대비압축) → 양성 생성.
- 두 분석기를 채점·비교:
  - BASELINE: degraded(마스크 없음). 톤 배경/흉상은 '측정 보류'(rr=None) → 커버리지 낮음.
  - MASKED  : 피사체 마스크로 figure_value_range 채움 → 흉상도 측정 가능.
- 출력: 커버리지(측정가능 장수) + 현재 임계 recall/FPR + severity별 recall + 임계 sweep ROC.
- `--base-only` / `--mask-only` 로 한쪽만.

## 핵심 설계
- 변형 = 분석기가 *재는 구성개념*과 일치(밝기 곱이 아니라 **명도 범위 압축**). 톤 배경도 처리.
- analyzer.py 가 **진짜 diagnose 의 image_signals + s_value_structure** 를 호출(사본 아님).
- 마스크는 pipeline/mask.py 의 region_signals_from_mask 로 figure 신호를 채움 — diagnose 의
  region_signals(pose 기반)와 *동일 계약*. 그래서 하니스가 검증한 게 곧 production figure 경로.
- 출력은 단일 숫자가 아니라 **곡선** → 운용 임계를 데이터로 고른다.

## 마스크 품질
- 기본(의존성 0): paper(흰 종이=자국 임계) / 중앙박스∩배경톤제외(흉상 근사). 거칠다.
- 더 나은 분할: `pip install rembg` → subject_mask 가 자동으로 rembg 사용(살리언트 분할).
- 어느 마스크가 실제로 recall 을 올리는지는 *이 하니스가 판정*한다.

## 검증된 동작(합성 톤배경 흉상)
- BASELINE: 커버리지 0/32, recall 0.00 (흉상 측정 불가 = 그동안의 문제).
- MASKED  : 커버리지 32/32, 임계 0.35에서 recall 1.00 / FPR 0.00.
→ 실제 흉상 수치는 당신 그림으로 돌려서 확인.

## 다음
- 마스크가 baseline 을 이기면 → diagnose.region_signals 에 pose 실패 시 subject_mask 폴백 통합.
- 축 확장: contrast → exposure → 구도 shift → 비율(FBX).
