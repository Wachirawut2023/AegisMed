# AegisMed container image.
# The hackathon requires all submissions to be containerized — this file does that.
# Build:  docker build --platform linux/amd64 -t aegismed .
# Run:    docker run -p 8000:8000 --env-file .env aegismed
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code AND its data: the knowledge base, guideline index,
# and demo cases live in data/ and are loaded by aegismed/knowledge.py and
# aegismed/guidelines.py at import time. Without this the container would boot
# but silently run with an empty knowledge base (no Orphanet/OMIM citations).
COPY aegismed/ aegismed/
COPY static/ static/
COPY data/ data/

EXPOSE 8000

# Liveness probe for Docker/orchestration — hits the same /health endpoint judges
# and uptime checks use. Uses stdlib urllib (no curl in python:3.11-slim).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "aegismed.main:app", "--host", "0.0.0.0", "--port", "8000"]
