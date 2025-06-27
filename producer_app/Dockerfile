# File: producer_app/Dockerfile (Versi Final yang Benar)
FROM python:3.9-slim

WORKDIR /app

# Hanya salin kode dan dependensinya
COPY requirements.txt .
COPY producer.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "producer.py"]