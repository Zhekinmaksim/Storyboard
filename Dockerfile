# Storyboard API — Fly.io image.
#
# Single Python process, system librsvg for PNG export and ImageMagick
# for animated GIF export, no node, no build step.

FROM python:3.12-slim

# librsvg2-bin gives us rsvg-convert for SVG → PNG. imagemagick provides
# convert for board.gif assembly. curl is just for healthchecks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        librsvg2-bin \
        imagemagick \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so the layer caches.
COPY pyproject.toml /app/
RUN pip install --no-cache-dir 'httpx>=0.27'

# Copy the rest of the project
COPY scripts /app/scripts
COPY web /app/web

# Storyboard outputs go to a writable location inside the container.
# Fly volumes can be mounted here later if persistence matters.
ENV STORYBOARD_OUTPUT_DIR=/data/storyboard-output \
    STORYBOARD_JOBS_DIR=/data/storyboard-jobs \
    STORYBOARD_CACHE_DIR=/data/cache

RUN mkdir -p /data/storyboard-output /data/storyboard-jobs /data/cache

# Fly assigns PORT env var; web_server.py reads it.
EXPOSE 8080

# Healthcheck hits /api/health every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8080}/api/health || exit 1

CMD ["python", "-m", "scripts.web_server"]
