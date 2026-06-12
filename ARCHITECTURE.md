# artcoach — 아키텍처 & 설계

이 문서는 [README](./README.md)의 심화판입니다 — **제품 개요는 README**, **내부 동작·근거·운영은 여기서** 다룹니다.

---

## 1. 설계 배경 — "피드백 도구"에서 "성장 시스템"으로

초기 컨셉은 *그림 한 장에 대한 단편 피드백*이었습니다. 멘토링을 거쳐 방향을 바꿨습니다.

| | 기존 (피드백 도구) | 지금 (성장 시스템) |
|---|---|---|
| 입력의 의미 | 그림 → 피드백 | 그림 → **진단 + 성장 경로 갱신 트리거** |
| 출력 | 개선 포인트 한 줄 | 관찰 코칭 **+ "지금 어디 / 다음 무엇"** |
| 컨텍스트 | 매번 단발 | **반복할수록 이 사람을 아는 상태**(로드맵 누적) |
| 포지션 | 그림 봐주는 AI | **그림 실력 키워주는 코치** |

> 핵심 한 문장 — *"사용자가 그림을 올리면, AI는 피드백을 주는 게 아니라 그 사람의 성장 커리큘럼 위에서 다음 한 걸음을 설계해준다."*

---

## 2. 핵심 원칙의 불변식

4원칙 중 가장 까다로운 건 **"평가하지 않는다"와 "성장 로드맵이 있다"의 공존**입니다.

점수·등급·실력 판정을 사용자에게 내리지 않습니다 — *초보·고수·잘 그렸다·못 그렸다·점수* 같은 표현은 가드레일이 차단합니다. 동시에, 초보→중급으로 나아가는 로드맵은 분명히 존재하되 **내부적으로만** 갖습니다.

> **불변식** — 내부 성장 단계(`growth_stage`의 foundation→developing→refining)와 레벨 추정은 **절대 사용자에게 라벨로 노출되지 않습니다.** 하는 일은 둘뿐입니다: ① 첫 업로드 때 "어디서부터 같이 볼지"(진입 축)를 그림에서 고르고, ② 코칭 순서·톤의 내부 힌트가 됩니다. "실력을 판정"하는 게 아니라 *커리큘럼의 어느 지점에서 함께 보면 효과적인가*만 정합니다. 이래서 "평가하지 않는다"와 "성장 로드맵"이 충돌하지 않습니다.

가드레일은 응답에서 ① 스키마 ② 닫힌 세계(주어진 sub-problem·검색된 ref만) ③ 금지 표현(평가어·레벨어) ④ 근거 존재를 검증하고, 실패 시 재시도 후 근거 기반 템플릿으로 폴백합니다. **`/guide`와 `/guide/stream` 양쪽 모두** 이 검증을 거칩니다(검증된 블록만 흘립니다).

---

## 3. 파이프라인 상세

```
업로드(그림 + 메시지)
   ↓ 정규화(EXIF·RGB·리사이즈, HEIC) → 안전 스크리닝(비-작품/유해 게이트)
   ↓ 장면 분석(CLIP 제로샷) → 포즈 추출(MediaPipe Tasks, 33 키포인트)
   ↓ 라우팅(생성요청→리다이렉트 / 비작품→확인 / 그 외→코칭)
   ↓ 성장 컨텍스트 로드(growth_context: 커리큘럼·이력·콜드스타트 여부)
   ↓ 진단(taxonomy 기반 · 기하/명도/색/빛 신호 · 성장 이력으로 랭킹 보정)
   ↓ 콜드스타트면 진입 집중 축을 '측정된 약점'으로 교정
   ↓ 레퍼런스 검색(Qdrant 벡터 검색 · commercial_ok 하드필터)
   ↓ 코칭 생성(LLM, 관찰별 블록) → 가드레일 검증(스키마·닫힌세계·금지표현·근거)
   ↓ 로드맵 반영(노출 'seen' 누적 → 다음 호출의 성장 컨텍스트로)
   ↓ 응답 반환(GuideResponse: blocks + next_steps + 로드맵 앵커)
```

---

## 4. 진단 체계 (Taxonomy)

`api/schema/taxonomy.yaml`의 **14개 하위 문제**로 동작합니다. 각 항목은 `personas`(어떤 맥락에서 떠오르는지)로 묶이고, 일부는 그림에서 자동 측정되며(`auto`), 일부는 언급·persona로 떠오릅니다. 자동 측정 신호는 키포인트 기하·명도/색 통계 기반 **휴리스틱(임계값)** 이며 학습된 진단 모델이 아닙니다 — 신호가 약하면 신뢰도가 낮게 유지되어 단정 대신 가설형으로 안내됩니다.

| id | personas | 자동 측정 |
|----|----------|:--------:|
| `proportion` | pose, anatomy | ✅ |
| `weight_balance` | pose, anatomy | ✅ |
| `action_line` | pose | ✅ |
| `joint_articulation` | pose, anatomy | ✅ |
| `foreshortening` | pose, anatomy, perspective | ✅ |
| `value_structure` | light, technique | ✅ |
| `composition_balance` | composition | ✅ |
| `atmospheric_perspective` | perspective, light | ✅ (풍경) |
| `horizon_placement` | composition | ✅ (풍경) |
| `color_harmony` | color | ◯ 보수적 image 신호 |
| `light_direction` | light | ◯ 보수적 image 신호 |
| `hand_structure` | hand, anatomy | ◯ `HAND_AUTO`일 때(손 레퍼런스 적재 후) |
| `linear_perspective` | perspective, composition | — (언급·persona) |
| `depth_layering` | composition, perspective | — (언급·persona) |

> ◯ = 스코어러는 있으나 보수적 임계값/환경 게이팅으로 동작(데이터로 튜닝 대상). — = 자동 측정 없이 surface만.

### Signal 예시
```json
{ "com_offset": 0.17, "torso_lean": 0.04, "leg_torso_ratio": 1.62,
  "arm_proj_ratio": 0.55, "elbow_angle_min": 178.4, "knee_angle_min": 162.1,
  "value_std": 0.14, "focus_centeredness": 0.92 }
```

---

## 5. 성장 시스템 내부

`pipeline/roadmap.py` + `pipeline/profiles.py` + `pipeline/growth_stage.py`가 LLM 없이 결정적으로 동작합니다.

### 커리큘럼 — "구조 먼저"
성장 순서를 인코딩합니다: 큰 구조(비율·무게·동세) → 사지(관절·단축) → 손 → 빛/명암 → 구도/색. *"왜 다음에 손을 연습하나"* = 손 앞의 구조 단계가 어느 정도 자리잡은 뒤가 효과적이라는 것.

### track 프로파일 — 장르 기반 분기
커리큘럼·게이팅·측정 norm을 한 덩어리로 갈아끼웁니다.

| track | 설명 | 비율 norm |
|---|---|---|
| `realistic_figure` | 사실체 인물(7~8등신) | 적용 |
| `anime_figure` | 애니/웹툰(다리 길게) | 적용 |
| `chibi_figure` | 치비/SD(머리 크게) | 적용 |
| `landscape` | 풍경/정물(원근·대기·깊이·지평선) | 끔 |
| (자동) | 인물 유무로 자동 — 스타일 미상이면 비율 자동 발화를 꺼 오발화 방지 | 끔 |

### 진척 상태머신 + 콜드스타트
- 축별 상태: `new → practicing → improving → steady` (연습 이력 + 최근 진단으로 휴리스틱 전이).
- **자주 막히는 부분(recurring)**, **추세(개선/악화/유지)**, **현재 집중 → 다음 목표 → 왜**를 만든다.
- **콜드스타트(첫 업로드, 이력 0)**: 진입 집중 축을 *그 그림에서 측정된 약점* 중 커리큘럼 앞쪽 것으로 잡습니다. 구조가 탄탄한 첫 그림은 자연히 더 뒤 단계에서 시작합니다(개인화). → **업로드 = 진단 + 성장 경로 설정 트리거.**

### 목표 핀 — N장 기준 닫힌 루프
로드맵은 매 호출마다 집중 축을 새로 고르지 않고, **하나의 목표 축을 고정(pin)** 한 뒤 달성할 때까지 유지합니다. 달성하면 커리큘럼상 **다음 축으로 자동 진급**합니다.
- **고정 대상**: 실제 약점인 축만 핀(약점이 없으면 핀 안 함 → 과한 목표 강요 방지).
- **달성 판정(하이브리드)**: ① 그 축이 `steady`로 졸업했거나, ② 고정 후 `GOAL_MIN_WINDOW`(기본 2장) 이상 지났는데 최근 창에서 안 보임. → 시간이 아니라 **업로드 N장 기준**.
- **노출**: `GET /roadmap`이 `goal` 필드(`sub_problem` · `status` · `baseline_count`/`current_count` · `uploads_since` · `just_achieved`)를 반환하고, UI는 가이드에 **"이번 목표 + 진행/🎉달성→다음 목표"** 배너로 보여줍니다.
- **안전성**: 모든 단계 try/except로 실패 시 `goal=None` 폴백 → 기존 동작 보존. `user_goal` 테이블은 지연 생성하므로 별도 마이그레이션 없이도 동작하며, 정식 기록은 `006_user_goal.sql`.

이로써 `관찰 → 우선순위(집중 축) → 코칭/연습 → 측정(다음 업로드)`이 **닫힌 루프**가 됩니다 — 한 장의 코칭이 같은 목표의 진척으로 누적되고, 달성하면 스스로 다음 단계로 넘어갑니다.

### UI에서의 노출
가이드 최상단에 **로드맵 앵커**("지금은 X에 집중 → 이게 안정되면 Y")가 항상 떠서, *이 한 장의 코칭이 성장 경로의 어디인지* 보여줍니다. 별도 **성장 흐름** 화면에서 전체 사다리·추세·자주 막히는 부분을 봅니다.

---

## 6. 레퍼런스 시스템

코칭은 검색된 레퍼런스를 기반으로 진행됩니다. **상업적으로 사용 가능한 자료만** 사용합니다.

- The Met Open Access (CC0)
- 자체 제작 Blender 렌더 (MakeHuman 기반 CC0 캐릭터)
- 자체 구축 포즈 라이브러리 + 교육용 구축선/레퍼런스 SVG 도식
- **AI 예제** — **Bria** text-to-image로 생성(라이선스 정리된 데이터로 학습된 상업용 모델). 생성 후 `ai_qc` 게이트(개념 일치·사진 거부·해부 검사)를 통과한 것만 `source_type=ai_example`로 적재.

> 생성기는 **비종속(generator-agnostic)** 입니다. 토큰/비용 사정으로 기존 Gemini → **Bria**로 전환했지만, 같은 `plan.json → manifest.jsonl` 규약을 공유하므로 QC·적재 경로는 그대로입니다. (`scripts/bria_generate.py`, 레거시 `scripts/gemini_generate.py`. 수요 가중 플랜은 `gen_plans/coverage_fill.json` — 코퍼스 감사에서 도출.)

### 검색 방식
Qdrant 벡터 검색에 `commercial_ok` 하드 필터 + source/persona/track/medium 소프트 부스트 + 피드백 리랭크 + 콜드스타트 탐색(노출 적은 레퍼런스를 가끔 끌어올림)을 적용합니다. 벡터 스토어는 어댑터(`stores/vectors.py` + `_vecfilter.py`)로 **백엔드 중립** — Qdrant/Pinecone를 같은 필터 규약으로 다룹니다.

임베더는 `ml/embed.py`가 `EMBEDDING_MODEL`(env)로 결정하며, 기본값은 **OpenCLIP `ViT-L-14:openai`(= `clip-vit-large-patch14`, 768차원)** 입니다. 차원은 하드코딩 없이 모델에서 가져와(`embedder.dim`) Qdrant 컬렉션 생성·검증에 사용하므로, 모델만 바꾸면 코드 수정 없이 차원이 따라갑니다.

### 피드백 리랭크
레퍼런스 카드의 **좋아요(👍)/싫어요(👎)** 와 채택·노출 로그를 `(sub_problem, ref_id)`별로 집계해 검색 점수에 ±보너스를 더합니다. 좋아요(`liked`)·클릭·저장은 ↑, **싫어요(`disliked`)는 강한 음수(−)로 다음 검색에서 그 레퍼런스를 내립니다.** 자주 노출됐는데 안 눌린 ref도 ↓(인기 편향 방지, CTR성 신호). 이 신호는 **'레퍼런스 유용성'에 대한 것이지 사용자 실력 판정이 아닙니다**(원칙 2 유지). 라플라스 스무딩 + 상·하한 캡으로 표본 적은 ref의 지배를 막습니다.

---

## 7. 안전 설계

- **업로드 스크리닝** — 비-작품 감지, 유해 콘텐츠 차단, 인물 신원 식별 방지.
- **가드레일 검증** — ① 응답 스키마 ② 닫힌 세계 ③ 금지 표현(평가어·레벨어) ④ 근거 존재. 실패 시 재시도 후 근거 기반 템플릿 폴백. **`/guide`·`/guide/stream` 양쪽** 적용.
- **내부 레벨링 비노출** — 성장 단계/레벨은 내부 신호이며 사용자 응답으로 새지 않습니다(§2 불변식).
- **접근 통제** — 선택적 API 키 + 레이트리밋으로 비용 남용·피드백 랭커 오염을 막습니다.

---

## 8. 접근 통제 · 배포

로컬은 키 없이 동작하지만, `.env`에 다음을 설정하면 공개 엔드포인트가 보호됩니다(미설정이면 비활성).

```
API_KEY=긴-랜덤-키            # X-API-Key 또는 Authorization: Bearer 로 요구(콤마로 다중 키)
RATE_LIMIT=60/minute          # 키/IP 별 한도
REDIS_URL=redis://redis:6379/0  # 여러 인스턴스면 한도 공유(없으면 in-process)
CORS_ORIGINS=https://your.app   # 허용 출처(woz 경로 사용 시 http://localhost:5173 포함)
```

설정 시 `/healthz`·`/docs`·`/test`·OPTIONS를 제외한 경로에 인증·레이트리밋이 적용됩니다.

### AI 예제 생성 (선택, Bria)
```bash
export BRIA_API_KEY=...                          # 백엔드 환경에만(프론트로 보내지 말 것)
python scripts/bria_generate.py gen_plans/coverage_fill.json --out /tmp/gen_out
python scripts/ingest_ai_examples.py /tmp/gen_out   # QC 게이트 통과분만 적재
```
> 컨테이너의 `/repo`는 읽기 전용이므로 `--out`은 쓰기 가능 경로(`/tmp/gen_out`)로 두고 거기서 적재하세요.

---

## 9. API

| Endpoint | 설명 |
|----------|------|
| `POST /analyze` | 진단 결과(관찰 후보 · 신뢰도 · 신호) |
| `POST /guide` | 코칭 응답 + 노출 로깅 + 로드맵 반영 |
| `POST /guide/stream` | 코칭 응답 SSE(가드레일 통과 블록 단위) |
| `POST /search` | 레퍼런스 검색(붙여넣기용 절대 URL 동봉) |
| `POST /adopt` | 반응 이벤트(클릭/저장/좋아요/싫어요) 기록 — **좋아요/싫어요는 검색 랭킹에 ±반영** |
| `GET /roadmap` | 현재 단계 → 다음 연습 → 다음 목표(+ N장 기준 고정 `goal`) + 사다리·추세·자주 막히는 부분 |
| `POST /practice` | 연습 이벤트(시도/나중에) 기록 |
| `GET /image/{ref_id}` | ref_id → presigned URL 리다이렉트 |
| `GET /guide-asset/{ref_id}` · `GET /svg/{ref_id}` | 교육용 도식/구축선 자산(이미지·SVG) |
| `POST /ai-example/qc` · `POST /ai-example/ingest` | AI 예제 QC 게이트 / 적재(통과분만 `source_type=ai_example`) |
| `GET /test` | FastAPI 단독 테스트 UI(같은-출처, 인증·CORS 면제) |
| `GET /healthz` | 헬스체크(인증·레이트리밋 면제) |

---

## 10. 평가 · CI

```bash
cd artref/api && python run_tests.py        # 커스텀 단위 테스트 전체(무거운 의존 없이)

python eval/eval.py --set safety    --labels eval/datasets/safety.json       # 금지표현 누출 + 모드 일치
python eval/eval.py --set retrieval --labels eval/datasets/retrieval.json    # recall@10 (Qdrant 필요)
python eval/eval.py --set diagnosis --labels eval/datasets/diagnosis_woz.json # primary_focus top-3 일치
```
GitHub Actions(`.github/workflows/tests.yml`)가 push/PR마다 백엔드 테스트와 프론트 빌드를 실행합니다.

---

## 11. 디렉터리 구조

```
.
├── .github/workflows/tests.yml   # CI: 백엔드 커스텀 테스트 + 프론트 build
├── artref/                       # 백엔드 + 인프라 + 평가 + 운영 스크립트
│   ├── api/
│   │   ├── main.py               # FastAPI 엔드포인트 + 접근통제 미들웨어
│   │   ├── _auth.py              # 선택적 API 키 인증(env API_KEY)
│   │   ├── _ratelimit.py         # 레이트리밋(env RATE_LIMIT, REDIS_URL 있으면 분산)
│   │   ├── _security.py          # ref_id 검증 · 이벤트 화이트리스트 · CORS
│   │   ├── ml/                   # embed · scene · pose · normalize · llm · guide · hands
│   │   ├── pipeline/             # router · diagnose · search · feedback · ingest
│   │   │   ├── roadmap.py        # 성장 로드맵(상태머신 · recurring · 추세 · 목표 핀)
│   │   │   ├── growth_stage.py   # 내부 성장 단계 · 콜드스타트(노출 금지)
│   │   │   ├── profiles.py       # track 커리큘럼 · 게이팅 · norm
│   │   │   └── ai_ingest.py · ai_qc.py  # AI 예제 QC 게이트
│   │   ├── safety/               # validate(가드레일) · moderation · screen
│   │   ├── stores/               # db(MySQL) · vectors(Qdrant) · s3(MinIO) · _vecfilter
│   │   ├── schema/               # ddl.sql · taxonomy.yaml(14축) · migrations
│   │   ├── tests/ · run_tests.py # 커스텀 t_ 러너(무거운 의존 없이 도는 단위 테스트)
│   │   ├── test_ui.html          # /test — FastAPI 단독 테스트 UI(같은-출처)
│   │   └── Dockerfile
│   ├── eval/                     # safety · retrieval · diagnosis 평가 harness
│   ├── scripts/                  # 시드 · 렌더 · bria_generate · ingest · 감사/튜닝 …
│   ├── gen_plans/                # 생성 플랜(coverage_fill.json 등) — 소스
│   └── docker-compose.yml        # mysql · qdrant · minio · api
└── woz/                          # 프론트엔드 (React + Vite)
    └── src/                      # GuideEntry(업로드→코칭 · 이번 목표 배너 · 레퍼런스 좋아요/싫어요)
                                  # NextSteps · Roadmap · GuideAsset …
```