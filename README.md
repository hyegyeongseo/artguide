# artcoach — 관찰 기반 그림 코칭 AI

> 그림을 대신 그려주지 않고,
> 사용자가 **더 잘 관찰하고 더 잘 수정할 수 있도록 돕는 AI 코치**
>
> 자유발화 조언이 아니라 **근거 기반 코칭 파이프라인** —
> `Signal → Taxonomy → Retrieval → Guide → Guardrail`

사용자가 업로드한 그림을 분석해 관찰 가능한 신호를 찾고, 관련 레퍼런스를 제시하며,
**관찰 → 효과 → 실험** 구조로 코칭을 제공합니다.

## 왜 만들었나

많은 AI 도구는 그림을 생성하거나 수정합니다. artcoach는 반대 방향을 지향합니다.
사용자의 그림을 대신 그리지 않고, 대신 함께 살펴봅니다.

- 무엇이 보이는지
- 왜 그렇게 보이는지
- 어떤 실험을 해볼 수 있는지

## 무엇이 다른가

흔한 드로잉 AI는 보통 셋 중 하나입니다.

- **생성형** (Midjourney · Stable Diffusion · DALL·E) — 텍스트로 이미지를 만든다.
- **자유발화 튜터형** — 그림을 올리면 LLM이 "비율이 별로"처럼 근거 없이 평한다(환각 · 레퍼런스 없음).
- **레퍼런스 검색형** — "손 포즈"를 검색하면 이미지를 나열한다(진단 없음).

artcoach의 핵심은 **LLM이 코칭하는 게 아니라, 진단 엔진이 코칭 방향을 결정하고 LLM 출력은 가드레일로 근거에 묶인다**는 점입니다. 자유발화가 아니라 *근거 기반 코칭 파이프라인*입니다.

```
일반 LLM 튜터               artcoach
──────────────             ─────────────────────────────
Image                       Image
  │                           │
  ▼                           ▼
LLM (자유발화)              Signal 추출   (측정된 신호)
  │                           │
  ▼                           ▼
Advice                      Taxonomy 진단 (어디를 볼지 결정)
(근거·검증 없음)              │
                              ▼
                            Reference 검색 (상업-클린 코퍼스)
                              │
                              ▼
                            Guide 생성    (LLM, 관찰별 블록)
                              │
                              ▼
                            Guardrail 검증 (근거·정책·스키마)
```

이 구조 덕분에 출력은 "지어낸 조언"이 아니라 **측정된 신호 + 검색된 레퍼런스에 묶인 관찰**이 됩니다. 진단·레퍼런스·코칭을 하나의 검증된 루프로 묶은 것이 이 프로젝트의 차별점입니다.

## 핵심 원칙

### 1. 대신 그리지 않는다

사용자의 그림을 수정하거나 완성하지 않습니다. "그려줘" 같은 생성 요청은 코칭 방향으로 리다이렉트됩니다.

### 2. 평가하지 않는다

점수·등급·실력 판정을 하지 않습니다. *초보·고수·잘 그렸다·못 그렸다·점수* 같은 표현은 가드레일이 차단합니다. 평가 대상은 사람이 아니라 그림이며, 칭찬도 평가로 보고 피합니다.

### 3. 관찰 가능한 것만 말한다

그림에서 자동 측정된 신호(`signal`)가 있을 때만 단정형으로 설명합니다. 측정되지 않은 부분은 가설형으로만 안내합니다.

> 손의 방향이 조금 모호하게 보이는지 같이 살펴봐요.

### 4. 닫힌 세계(Closed World)

LLM은 임의로 정보를 만들어내지 않습니다. 출력은 반드시 **taxonomy · 진단 결과 · 검색된 레퍼런스**만 사용하며, 검증에 실패하면 재생성하거나 근거 기반 템플릿으로 폴백합니다.

## 코칭 방식

각 관찰은 세 부분으로 구성되며, 서로 다른 내용이어야 합니다(반복 금지).

```
Observation  (관찰)  → 무엇이 어떻게 보이는지
   ↓
Effect       (효과)  → 그 상태가 보기에 어떤 차이를 만드는지
   ↓
Experiment   (실험)  → 지금 바로 해볼 수 있는 실험 한 가지
```

예시:

- **Observation** — 손목 방향이 손바닥 평면과 조금 다르게 보입니다.
- **Effect** — 손이 어느 방향을 향하는지 읽기 어려워질 수 있습니다.
- **Experiment** — 손등이 보이는 버전과 손바닥이 보이는 버전을 각각 스케치해 비교해보세요.

## 시스템 흐름

```
업로드(그림 + 메시지)
   ↓
정규화 (EXIF 보정 · RGB · 리사이즈, HEIC 지원)
   ↓
안전 스크리닝 (비-작품 / 유해물 게이트)
   ↓
장면 분석 (CLIP 제로샷: 인물 유무 · 작품 여부 · 카메라 · 조명)
   ↓
포즈 추출 (MediaPipe Tasks, 33 키포인트)
   ↓
라우팅 (생성요청→리다이렉트 / 비작품→확인 / 그 외→코칭)
   ↓
진단 (taxonomy 기반 · 기하/명도 신호)
   ↓
레퍼런스 검색 (Qdrant 벡터 검색)
   ↓
코칭 생성 (LLM, 관찰별 블록)
   ↓
가드레일 검증 (스키마 · 닫힌 세계 · 금지 표현)
   ↓
응답 반환 (GuideResponse)
```

## 진단 체계 (Taxonomy)

진단은 `api/schema/taxonomy.yaml`에 정의된 **10개의 하위 문제(sub-problem)** 로 동작합니다.
각 항목은 카테고리가 아니라 `personas`(어떤 맥락에서 떠오를지)로 묶이며, 일부는 그림에서
자동 측정되고(`auto`), 일부는 사용자의 언급이나 persona로 떠오릅니다.

| id | personas | 자동 측정 |
|----|----------|:--------:|
| `weight_balance` | pose, anatomy | ✅ |
| `foreshortening` | pose, anatomy, perspective | ✅ |
| `proportion` | pose, anatomy | ✅ |
| `action_line` | pose | ✅ |
| `joint_articulation` | pose, anatomy | ✅ |
| `value_structure` | light, technique | ✅ |
| `composition_balance` | composition | ✅ |
| `hand_structure` | hand, anatomy | — (언급·persona로) |
| `color_harmony` | color | — (언급·persona로) |
| `light_direction` | light | — (언급·persona로) |

> 자동 측정이 없는 항목은 결핍을 단정하지 않고, "함께 어디를 볼지"를 가설형으로만 안내합니다.
>
> 자동 측정 신호는 키포인트 기하·명도 통계에 기반한 **휴리스틱(임계값) 신호**이며, 학습된 진단 모델이 아닙니다. 신호가 약하면 신뢰도가 낮게 유지되어, 같은 항목이라도 단정 대신 가설형으로 안내됩니다.

## Signal 예시

진단은 추상적 의견이 아니라 측정 가능한 신호를 사용합니다. 아래는 포즈가 검출됐을 때
`diagnose`가 만드는 실제 신호의 예입니다.

```json
{
  "com_offset": 0.17,
  "torso_lean": 0.04,
  "leg_torso_ratio": 1.62,
  "arm_proj_ratio": 0.55,
  "elbow_angle_min": 178.4,
  "knee_angle_min": 162.1,
  "value_std": 0.14,
  "focus_centeredness": 0.92
}
```

## 레퍼런스 시스템

코칭은 검색된 레퍼런스를 기반으로 진행됩니다. 목표는 사용자가 "무엇을 고쳐야 하는가"뿐 아니라 "어떻게 관찰할 수 있는가"를 이해하도록 돕는 것입니다.

### 데이터 출처

상업적으로 사용 가능한 자료만 사용합니다.

- The Met Open Access (CC0)
- 자체 제작 Blender 렌더 (MakeHuman 기반 CC0 캐릭터)
- 자체 구축 포즈 라이브러리

### 검색 방식

Qdrant 벡터 검색에 다음을 적용합니다.

- `commercial_ok` 하드 필터
- source / persona 소프트 부스트
- 채택·노출(CTR성) 피드백 리랭크
- 콜드스타트 탐색(노출 적은 레퍼런스를 가끔 끌어올려 수렴 방지)

## 아키텍처

```
.
├── artref/                  # 백엔드 + 인프라 + 평가 + 운영 스크립트
│   ├── api/
│   │   ├── main.py          # FastAPI 엔드포인트
│   │   ├── ml/              # embed · scene · pose · normalize · llm · guide
│   │   ├── pipeline/        # router · diagnose · search · feedback · ingest
│   │   ├── safety/          # validate(가드레일) · moderation
│   │   ├── stores/          # db(MySQL) · vectors(Qdrant) · s3(MinIO)
│   │   ├── schema/          # ddl.sql · taxonomy.yaml · intake.yaml
│   │   ├── prompts.py       # 시스템 프롬프트 단일 출처
│   │   ├── schemas.py       # Pydantic 응답 스키마
│   │   └── Dockerfile
│   ├── eval/                # safety · retrieval · diagnosis 평가 harness
│   ├── scripts/             # 시드 · Blender 렌더 · DB 초기화 …
│   ├── render/              # Blender 배치 렌더러
│   ├── pose_viewer.html     # 포즈를 여러 각도로 둘러보는 단독 뷰어
│   └── docker-compose.yml   # mysql · qdrant · minio · api
│
└── woz/                     # 프론트엔드 (React + Vite) — 운영자 WoZ 테스트 페이지
    └── src/
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI |
| Validation | Pydantic |
| Embedding | OpenCLIP (ViT-B-32) |
| Pose | MediaPipe Tasks |
| Vector DB | Qdrant |
| Database | MySQL |
| Storage | MinIO (S3 호환) |
| Frontend | React + Vite |
| Infra | Docker Compose |
| LLM | Grok (선택, 미설정 시 오프라인 템플릿으로 동작) |

## 빠른 시작

### 1. 인프라 + API 실행

```bash
cd artref
cp .env.example .env      # 값 채우기
docker compose up -d --build
```

### 2. DB + 벡터 컬렉션 초기화

```bash
docker compose exec -w /repo api python scripts/init_db.py
docker compose exec -w /repo api python api/schema/qdrant_init.py
```

### 3. 레퍼런스 적재 (선택)

```bash
docker compose exec -w /repo api python scripts/seed_museum.py all
```

### 4. WoZ UI 실행

```bash
cd woz
npm install
npm run dev          # http://localhost:5173
```

API는 `http://localhost:8000`에서 동작하며 `/docs`에서 Swagger UI를 볼 수 있습니다.

## API

| Endpoint | 설명 |
|----------|------|
| `POST /analyze` | 진단 결과 (관찰 후보 · 신뢰도 · 신호) |
| `POST /guide` | 코칭 응답 + 노출 로깅 |
| `POST /guide/stream` | 코칭 응답 SSE 스트리밍 |
| `POST /search` | 레퍼런스 검색 (붙여넣기용 절대 URL 동봉) |
| `POST /adopt` | 채택 이벤트(클릭/저장/좋아요) 기록 |
| `GET /image/{ref_id}` | ref_id → presigned URL로 리다이렉트 |
| `GET /healthz` | 헬스체크 |

## 안전 설계

**업로드 스크리닝** — 비-작품 감지, 유해 콘텐츠 차단, 인물 신원 식별 방지.

**가드레일 검증** — ① 응답 스키마 ② 닫힌 세계(주어진 sub-problem·검색된 ref만) ③ 금지 표현 ④ 근거 존재 여부를 검사하고, 실패 시 재시도 후 근거 기반 템플릿으로 폴백합니다.

## 평가

```bash
# Safety — 금지 표현 누출 + 모드 일치
python eval/eval.py --set safety --labels eval/datasets/safety.json

# Retrieval — recall@10 (Qdrant 필요)
python eval/eval.py --set retrieval --labels eval/datasets/retrieval.json

# Diagnosis — WoZ 라벨 대비 primary_focus top-3 일치
python eval/eval.py --set diagnosis --labels eval/datasets/diagnosis_woz.json
```

## 현재 상태

**구현 완료**

- 이미지 업로드 · 정규화 · 안전 스크리닝
- 포즈 추출(MediaPipe Tasks)
- 자동 진단 7종: `weight_balance` · `foreshortening` · `proportion` · `action_line` · `joint_articulation` · `value_structure` · `composition_balance`
- Qdrant 벡터 검색 + 레퍼런스 추천
- 채택/노출 피드백 리랭크
- 가드레일 검증 + 템플릿 폴백
- WoZ 테스트 UI

**진행 중**

- `hand_structure` · `color_harmony` · `light_direction`의 자동 측정 (현재는 사용자 언급·persona로 surface)
- 자체 렌더 레퍼런스 라이브러리 확충
- 피드백 데이터 축적을 통한 랭킹 개선

## 비전

artcoach는 그림을 대신 그리는 AI가 아닙니다.
사용자가 **더 잘 관찰하고, 더 잘 이해하고, 더 잘 연습할 수 있도록** 돕는 관찰 기반 창작 코치를 목표로 합니다.