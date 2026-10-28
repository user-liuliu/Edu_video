FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EV_RENDER_EXECUTABLE=/usr/bin/chromium EV_FFMPEG=/usr/bin/ffmpeg EV_FFPROBE=/usr/bin/ffprobe
WORKDIR /render
COPY renderer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && apt-get update && apt-get install -y --no-install-recommends chromium ffmpeg fonts-noto-cjk && rm -rf /var/lib/apt/lists/* && useradd --uid 10002 --no-create-home render
COPY backend/app/videos /render/app/videos
COPY backend/app/studio /render/app/studio
COPY backend/app/presentations/graphic_contract.py /render/app/presentations/graphic_contract.py
COPY backend/app/presentations/text_layout.py /render/app/presentations/text_layout.py
COPY renderer /render/renderer
USER 10002:10002
CMD ["uvicorn","renderer.app:app","--host","0.0.0.0","--port","8010","--workers","1","--no-access-log","--limit-concurrency","4"]
