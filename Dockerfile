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

# Only the JSON the running app actually reads at import time (knowledge.py's
# citations index, guidelines.py's curated index, main.py's demo-cases list)
# — not the dataset-builder scripts or eval fixtures (build-time/offline
# only), and not data/cases.jsonl, which is runtime state the app creates
# itself on first save.
COPY data/citations_index.json data/guidelines_index.json data/demo_cases.json ./data/

# Run as a non-root user. Own /app (including data/, where cases.jsonl gets
# created at runtime) so the app can still write there as this user.
RUN useradd --create-home --uid 1000 aegismed && chown -R aegismed:aegismed /app
USER aegismed

EXPOSE 8000

CMD ["uvicorn", "aegismed.main:app", "--host", "0.0.0.0", "--port", "8000"]
