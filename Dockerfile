# Base image: official Playwright Python image — multi-arch (amd64 + arm64), browsers
# and OS-level dependencies pre-installed. Matches the constitution's Compute Profile
# constraint (Arm Ampere A1, CPU-only) and Technology & Platform Constraints.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # Re-run browser install to match the exact Playwright pip version above —
    # the base image bundles browsers for its own build-time version only.
    && python -m playwright install chromium

COPY app/ ./app/

ENV PORT=8000
EXPOSE 8000

# Zeabur (and most PaaS platforms) inject $PORT at runtime; uvicorn must honor it.
CMD ["sh", "-c", "python -m uvicorn app.web.server:app --host 0.0.0.0 --port ${PORT}"]
