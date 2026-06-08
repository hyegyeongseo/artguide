import boto3
from botocore.config import Config
from config import settings

# 컨테이너 내부 통신용(put/get) — minio:9000
s3 = boto3.client("s3", endpoint_url=settings.s3_endpoint,
                  aws_access_key_id=settings.s3_key,
                  aws_secret_access_key=settings.s3_secret)

# presign 전용 — '브라우저가 닿는' 주소(localhost:9000)로 서명.
# generate_presigned_url은 네트워크 연결을 안 하므로(순수 서명), 이 주소가
# 컨테이너에서 실제로 닿지 않아도 무방. 서명 host == 브라우저 요청 host 라서 MinIO 검증 통과.
_presign = boto3.client("s3", endpoint_url=settings.s3_public_endpoint,
                        aws_access_key_id=settings.s3_key,
                        aws_secret_access_key=settings.s3_secret,
                        config=Config(signature_version="s3v4",
                                      s3={"addressing_style": "path"}))


def put_image(key: str, data: bytes, content_type: str = "image/png"):
    s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


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
