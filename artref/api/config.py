from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_dsn: str
    qdrant_url: str
    s3_endpoint: str
    s3_key: str
    s3_secret: str
    s3_bucket: str = "artref"
    # presigned URL 서명용 '브라우저가 닿는' 주소. 컨테이너 내부 통신은 s3_endpoint(minio:9000),
    # 브라우저 열람은 이 주소(localhost:9000). 배포 시 실제 공개 도메인으로.
    s3_public_endpoint: str = "http://localhost:9000"
    embedding_model: str
    qdrant_collection: str = "reference_images"
    llm_provider: str = ""        # 비우면 DummyLLM. "grok" 등 비우지 않으면 RealLLM(xAI)
    llm_model: str = ""           # 비우면 grok-4.3
    xai_api_key: str = ""         # XAI_API_KEY
    redis_url: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
