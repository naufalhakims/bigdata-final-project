# Menggunakan base image Python
FROM python:3.9-slim

# Menetapkan direktori kerja di dalam container
WORKDIR /app

# Menyalin file requirements.txt terlebih dahulu untuk optimasi cache
COPY ./streamlit/requirements.txt /app/requirements.txt

# Menginstal semua library Python yang dibutuhkan
RUN pip install --no-cache-dir -r requirements.txt

# Memberi tahu Docker bahwa container akan listen di port 8501
EXPOSE 8501

# Perintah default untuk menjalankan aplikasi Streamlit
CMD ["streamlit", "run", "app.py"]