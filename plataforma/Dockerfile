# Una sola imagen (multi-arquitectura: amd64 en la VM, arm64 en la Raspberry Pi) para
# los tres publicadores, el ingestor y el webhook de alertas.
FROM python:3.12-alpine
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
CMD ["python", "ingestor.py"]
