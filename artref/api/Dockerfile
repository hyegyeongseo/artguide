# 멀티아치 빌드 가능. python:3.11-slim 은 linux/amd64·linux/arm64 둘 다 제공.
# 빌드 컨텍스트는 ./api (docker-compose 의 build: ./api) → 이 Dockerfile 은 api/ 안에 둔다.
FROM python:3.11-slim
WORKDIR /app

# OpenCV(=mediapipe 의존) · mediapipe Tasks(GLES/EGL) 네이티브 .so 링크용.
# 이 패키지들은 arm64(arm64 multiarch apt)에도 동일하게 존재.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libegl1 libgles2 libopengl0 \
    && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사 → 소스만 바뀌면 무거운 pip 레이어 캐시 재사용.
COPY requirements.txt .
# CPU torch 를 '먼저' 설치 → 아래 -r 설치가 torch 를 이미 충족된 것으로 보고 CUDA(nvidia-*) 휠을 안 끌어옴.
#   GPU 없는 환경(로컬·ECS Graviton arm64)에서 CUDA 스택은 죽은 무게 → 이미지 ~6GB→~2GB대, 빌드도 단축.
#   ==2.12.0 은 CPU 채널의 2.12.0+cpu 휠과 매칭되어, requirements.txt 의 torch==2.12.0 도 그대로 충족(재설치 안 함).
#   (만약 CPU 채널에 해당 버전의 aarch64 휠이 없다고 나오면 버전 지정을 빼고 최신 CPU 를 받게 한다.)
RUN pip install --no-cache-dir torch==2.12.0 torchvision==0.27.0 \
        --index-url https://download.pytorch.org/whl/cpu
# arm64 에서 mediapipe(0.10.18+jax) 다운로드가 길 수 있어 타임아웃 여유.
RUN pip install --no-cache-dir --timeout 120 -r requirements.txt

COPY . .

# 컨테이너 헬스체크 — /healthz 는 인증 면제 경로. 배포/오케스트레이터가 기동 판정에 사용.
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=4).status==200 else 1)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]