FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# FastAPI의 Form/UploadFile(/guide·/analyze·/search·/adopt)에 필요.
# 별도 RUN으로 둬서 위 무거운 pip 레이어 캐시를 유지 → 재빌드가 빠름.
RUN pip install --no-cache-dir python-multipart
# mediapipe Tasks API가 GLES/EGL .so를 동적 링크 → slim 이미지에 추가(libGLESv2.so.2 등).
# 별도 RUN으로 둬서 위 무거운 pip 레이어 캐시를 유지 → 재빌드 빠름.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libegl1 libgles2 libopengl0 && rm -rf /var/lib/apt/lists/*
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
