FROM python:3.11-slim

WORKDIR /app

# Create credentials directory
RUN mkdir -p /app/credentials

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Create non-root user and switch to it
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV GOOGLE_CREDENTIALS_PATH=/app/credentials/google-sa.json

CMD ["python", "server.py"]
