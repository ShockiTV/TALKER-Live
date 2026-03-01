# Shared TTS microservice for TALKER
# Base image provides pocket_tts + all native dependencies.
FROM ghcr.io/kyutai-labs/pocket-tts:latest

WORKDIR /app

# Install Python dependencies (pocket_tts already installed in base image)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Voice files are mounted at runtime (docker-compose volume)
# ENV VOICES_DIR=/app/voices

EXPOSE 8100

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
