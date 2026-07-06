# Base image: the official "python" Docker Library image is a genuinely multi-arch
# manifest list (amd64, arm64/v8, ...) maintained by Docker's own library team — unlike
# mcr.microsoft.com/playwright/python, which is amd64-only today. Matches the
# constitution's Compute Profile constraint (Arm Ampere A1, CPU-only).
#
# --platform=linux/arm64 is pinned explicitly: a multi-arch base image alone is NOT
# enough. Without this, `docker build` resolves the base image to whatever architecture
# the BUILD machine itself is (almost always amd64 on cloud build farms), producing an
# amd64 image regardless of the runtime target — which is exactly what caused the first
# two Zeabur deploy attempts to fail with "exec format error" even after switching to a
# genuinely multi-arch base. Pinning the platform forces BuildKit to build for arm64
# (via QEMU emulation if the build host is amd64), matching the actual Ampere A1 runtime.
FROM --platform=linux/arm64 python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
# --with-deps runs Playwright's own OS-dependency installer (apt) for whatever
# architecture this build actually runs on, so it works correctly on arm64 too — it
# does NOT rely on a pre-baked, architecture-specific browser layer.
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY app/ ./app/

ENV PORT=8000
EXPOSE 8000

# Zeabur (and most PaaS platforms) inject $PORT at runtime; uvicorn must honor it.
CMD ["sh", "-c", "python -m uvicorn app.web.server:app --host 0.0.0.0 --port ${PORT}"]
