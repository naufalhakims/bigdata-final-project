# File: spark/stream/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Hanya salin file yang dibutuhkan untuk menjalankan aplikasi
COPY requirements.txt .
COPY producer.py .

# Instal dependensi
RUN pip install --no-cache-dir -r requirements.txt

# Perintah untuk menjalankan producer
CMD ["python", "producer.py"]