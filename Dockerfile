# Matches requirements.txt (playwright 1.57). Browser deps included in base image.
FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/*.sh 2>/dev/null || true

# Chromium is preinstalled in this image; no separate playwright install needed.
CMD ["python", "run_all.py"]
