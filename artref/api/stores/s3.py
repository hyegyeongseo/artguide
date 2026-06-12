import boto3
from botocore.config import Config
from config import settings

# 컨테이너 내부 통신용(put/get) — minio:9000
s3 = boto3.client("s3", endpoint_url=settings.s3_endpoint,
                  aws_access_key_id=settings.s3_key,
                  aws_secret_access_key=settings.s3_secret)

# presign 전용 — '브라우저가 닿는' 주소(localhost:9000)로 서명.
_presign = boto3.client("s3", endpoint_url=settings.s3_public_endpoint,
                        aws_access_key_id=settings.s3_key,
                        aws_secret_access_key=settings.s3_secret,
                        config=Config(signature_version="s3v4",
                                      s3={"addressing_style": "path"}))


def put_image(key: str, data: bytes, content_type: str = "image/png"):
    s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


def put_svg(key: str, data):
    """구축선 SVG 저장(Phase 4). data 는 str 또는 bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data,
                  ContentType="image/svg+xml")


def get_image(key: str) -> bytes:
    """S3에서 원본 바이트를 다시 읽음(재임베딩/복구 = S3→벡터DB 재색인용)."""
    return s3.get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()


def ensure_bucket():
    try:
        s3.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        s3.create_bucket(Bucket=settings.s3_bucket)


def presigned_url(key: str, expires: int = 3600) -> str:
    """브라우저에서 바로 열람 가능한 임시 GET URL (localhost:9000으로 서명)."""
    return _presign.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )
