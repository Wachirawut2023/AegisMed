# AegisMed container image.
# The hackathon requires all submissions to be containerized — this file does that.
# Build:  docker build -t aegismed .
# Run:    docker run -p 8000:8000 --env-file .env aegismed
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY aegismed/ aegismed/
COPY static/ static/
# Knowledge base, guideline index, and demo/example cases — read at runtime
# by aegismed/knowledge.py, guidelines.py, and main.py. Without this the app
# still boots but with an empty knowledge base (0 diseases) and no demo cases.
COPY data/ data/

EXPOSE 8000

# Cloud Run injects PORT (usually 8080) and requires listening on it; local
# Docker/Compose runs don't set PORT, so this falls back to 8000.
CMD ["sh", "-c", "uvicorn aegismed.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
