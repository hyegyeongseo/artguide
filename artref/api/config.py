from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 선언된 필드만 읽고, HAND_AUTO/AI_QC_* 같은 운영 env(.env에 있어도)는 무시 — extra_forbidden 방지.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    db_dsn: str
    qdrant_url: str = ""          # 개발(qdrant) 백엔드에서만 필요. pinecone 운영이면 비워도 됨.
    qdrant_api_key: str = ""      # QDRANT_API_KEY — Qdrant Cloud 인증용. 로컬(키 불필요)이면 비움.
    s3_endpoint: str
    s3_key: str
    s3_secret: str
    s3_bucket: str = "artref"
    # presigned URL 서명용 '브라우저가 닿는' 주소. 컨테이너 내부 통신은 s3_endpoint(minio:9000),
    # 브라우저 열람은 이 주소(localhost:9000). 배포 시 실제 공개 도메인으로.
    s3_public_endpoint: str = "http://localhost:9000"
    embedding_model: str
    qdrant_collection: str = "reference_images"
    # 벡터 DB 백엔드 — 개발은 qdrant(로컬 도커, 키 불필요), 운영은 pinecone(매니지드). stores/vectors.py 가 이걸로 분기.
    vector_backend: str = "qdrant"          # "qdrant" | "pinecone"
    pinecone_api_key: str = ""
    pinecone_index: str = "reference-images"
    pinecone_namespace: str = ""
    llm_provider: str = ""        # 비우면 DummyLLM. "grok" 등 비우지 않으면 RealLLM(xAI)
    llm_model: str = ""           # 비우면 grok-4.3
    xai_api_key: str = ""         # XAI_API_KEY
    gemini_api_key: str = ""      # GEMINI_API_KEY (레거시 생성기 — bria 로 대체)
    bria_api_key: str = ""        # BRIA_API_KEY (AI 예제 이미지 생성)
    bria_model: str = "2.3"       # BRIA_MODEL (Bria text-to-image base 모델 버전)
    redis_url: str = ""           # 있으면 레이트리밋을 분산 공유(없으면 in-process)
    # 접근 통제(둘 다 비면 비활성 = 로컬/WoZ/테스트 그대로):
    api_key: str = ""             # API_KEY — 설정 시 보호 경로에 X-API-Key/Bearer 요구(콤마로 다중 키)
    rate_limit: str = ""          # RATE_LIMIT — 예: "60/minute". 비면 레이트리밋 끔

settings = Settings()
