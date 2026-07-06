# Base image: the official "python" Docker Library image is a genuinely multi-arch
# manifest list (amd64, arm64/v8, ...) maintained by Docker's own library team — unlike
# mcr.microsoft.com/playwright/python, which is amd64-only today. Matches the
# constitution's Compute Profile constraint (Arm Ampere A1, CPU-only).
FROM python:3.11-slim-bookworm

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
