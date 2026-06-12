# artcoach — 관찰 기반 그림 **성장 코치** AI

> 그림을 대신 그려주는 AI가 아니라,
> 사용자가 **더 잘 관찰하고, 반복되는 약점을 인식하며, 한 장씩 실력을 쌓도록 돕는 코칭 시스템.**

사용자가 그림을 올리면 단편 피드백이 아니라 **무엇이 반복해서 문제인지 · 지금 어디를 보면 되는지 · 다음에 한 번 연습할 것**을 *성장 경로 위에서 연결해* 제공합니다.

---

## 무엇이 다른가

흔한 드로잉 AI는 보통 셋 중 하나입니다.

- **생성형**(Midjourney · Stable Diffusion · DALL·E) — 텍스트로 이미지를 만든다.
- **자유발화 튜터형** — 그림을 올리면 LLM이 근거 없이 "비율이 별로"처럼 평한다(환각 · 레퍼런스 없음).
- **레퍼런스 검색형** — 이미지를 나열만 한다(진단도 성장도 없음).

artcoach의 핵심은 두 가지입니다.

1. **진단 엔진이 코칭 방향을 정하고, LLM 출력은 가드레일로 근거에 묶인다** — 자유발화가 아니라 *근거 기반 코칭 파이프라인*.
2. **한 장의 코칭이 성장 로드맵의 한 지점으로 연결된다** — 단편이 아니라 *누적되는 커리큘럼*.

```
일반 LLM 튜터              artcoach
─────────────             ─────────────────────────────
Image                      Image
  ↓                          ↓
LLM (자유발화)             Signal 추출  →  Taxonomy 진단
  ↓                          ↓
Advice                     Reference 검색 (상업-클린 코퍼스)
(근거·검증 없음)             ↓
                           Guide 생성  →  Guardrail 검증
                             ↓
                           Roadmap 반영 (반복 패턴 · 목표 핀)
```

---

## 핵심 원칙

1. **대신 그리지 않는다** — 그림을 수정·완성하지 않습니다. "그려줘" 류 요청은 코칭으로 리다이렉트됩니다.
2. **평가하지 않는다** — 점수·등급·실력 판정을 사용자에게 내리지 않습니다. 성장 로드맵은 **내부적으로만** 존재하며, 내부 단계·레벨은 절대 라벨로 노출되지 않습니다. *(공존 방식 → [ARCHITECTURE.md](./ARCHITECTURE.md))*
3. **관찰 가능한 것만 말한다** — 자동 측정된 신호가 있을 때만 단정형, 나머지는 가설형으로 안내합니다.
4. **닫힌 세계(Closed World)** — LLM은 taxonomy · 진단 결과 · 검색된 레퍼런스만 사용합니다. 검증 실패 시 재생성하거나 근거 기반 템플릿으로 폴백하며, **스트리밍도 비스트리밍과 똑같이 가드레일을 거칩니다.**

---

## 코칭 구조 — Observation → Effect → Experiment

각 관찰은 세 부분으로 구성되며, 서로 다른 내용이어야 합니다.

```
Observation  무엇이 어떻게 보이는지
Effect       그 상태가 보기에 어떤 차이를 만드는지
Experiment   지금 바로 해볼 수 있는 실험 한 가지
```

> 예 — *관찰*: 손목 방향이 손바닥 평면과 조금 다르게 보입니다. *효과*: 손이 어디를 향하는지 읽기 어려워질 수 있어요. *실험*: 손등이 보이는 버전과 손바닥이 보이는 버전을 각각 스케치해 비교해보세요.

---

## 성장 시스템 (핵심 차별점)

업로드 한 장이 **진단 + 성장 경로 갱신 트리거**가 됩니다. LLM 없이 결정적으로 동작합니다.

- **반복 패턴 인식** — 자주 막히는 약점을 자동 추적(`flag_count` 기반 우선순위).
- **목표 핀(Goal Pin)** — 하나의 약점 축을 고정하고 **업로드 N장 기준**으로 진행/달성을 판정. 달성하면 커리큘럼상 다음 축으로 자동 진급합니다.
- **닫힌 루프** — `업로드 → 진단 → 연습 → 재측정 → 다음 목표`가 이어져, 단발 피드백이 아닌 **누적 성장 구조**가 됩니다.
- **커리큘럼** — "구조 먼저": 큰 구조(비율·무게·동세) → 사지 → 손 → 빛/명암 → 구도/색. 장르 track(사실체/애니/치비/풍경)으로 통째 분기합니다.

> 상태머신 · 콜드스타트 · 내부 레벨링 불변식 · track norm 등 깊은 동작은 **[ARCHITECTURE.md](./ARCHITECTURE.md)** 참고.

---

## 시스템 흐름

```
업로드(그림 + 메시지)
  ↓ 정규화 · 안전 스크리닝(비-작품/유해 게이트)
  ↓ 장면 분석(CLIP) · 포즈 추출(MediaPipe Tasks, 33 키포인트)
  ↓ 라우팅(생성요청 → 리다이렉트 / 그 외 → 코칭)
  ↓ 진단(taxonomy 14축 · 기하/명도/색/빛 신호 · 성장 이력으로 보정)
  ↓ 레퍼런스 검색(벡터 · commercial_ok 하드필터 · 피드백 리랭크)
  ↓ 코칭 생성(LLM) → 가드레일 검증(스키마·닫힌세계·금지표현·근거)
  ↓ 로드맵 반영 → 응답(blocks + next_steps + 로드맵 앵커)
```

---

## 레퍼런스 — 상업 사용 가능한 자료만

The Met Open Access(CC0), 자체 Blender 렌더(MakeHuman CC0), 자체 포즈·구축선 SVG 도식, 그리고 **Bria** text-to-image로 생성 후 QC 게이트를 통과한 **AI 예제**(`source_type=ai_example`)로 코퍼스를 구성합니다. 검색은 `commercial_ok` 하드필터 + 소프트 부스트 + **좋아요/싫어요 피드백 리랭크**(좋아요 ↑ / 싫어요 ↓)로 동작합니다.

---

## 기술 스택

FastAPI · Pydantic · OpenCLIP(ViT-B-32) · MediaPipe Tasks · Qdrant(벡터) · MySQL · MinIO(S3) · React + Vite · Docker Compose.
LLM은 선택(미설정 시 오프라인 템플릿), 이미지 생성은 Bria(선택, 오프라인 자산 생성용).

---

## 실행

로컬은 **키 없이** 동작합니다(LLM 미설정 시 오프라인 템플릿).

```bash
cd artref
cp .env.example .env
docker compose up -d --build
docker compose exec -w /repo api python scripts/init_db.py
docker compose exec -w /repo api python scripts/run_migrations.py
docker compose exec -w /repo api python api/schema/qdrant_init.py
```

- **API**: `http://localhost:8000` · Swagger: `/docs`
- **프론트(WoZ)**: `cd woz && npm install && npm run dev` → `http://localhost:5173`
- **테스트 UI**: `http://localhost:8000/test` — 프론트·Spring·CORS 없이 업로드→가이드를 바로 확인(코드 변경 후 `docker compose up -d --build api`로 리빌드)

> 접근 통제·엔드포인트·평가/CI 등 운영 항목은 **[ARCHITECTURE.md](./ARCHITECTURE.md)** 참고.

---

## 더 보기

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — 파이프라인 상세 · taxonomy 14축 · 성장 시스템 내부 · 검색/피드백 · 접근 통제 · API · 평가/CI · 디렉터리 구조
- **[CHANGES.md](./CHANGES.md)** — 변경 이력

---

## 비전

artcoach는 그림을 대신 그리는 AI가 아닙니다. 사용자가 **스스로 "무엇을 보고 있는지"를 학습하고, 한 장씩 쌓아 실력을 키워가도록** 돕는, 관찰 기반 **성장 코치**를 목표로 합니다.
