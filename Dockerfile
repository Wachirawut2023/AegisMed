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

EXPOSE 8000

CMD ["uvicorn", "aegismed.main:app", "--host", "0.0.0.0", "--port", "8000"]
