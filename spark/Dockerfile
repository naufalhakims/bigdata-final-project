# Menggunakan image bitnami/spark:3.4 sebagai dasar
FROM bitnami/spark:3.4

# Pindah ke user root sementara untuk bisa menginstal package
USER root

# Salin file requirements.txt yang baru kita buat ke dalam container
COPY ./requirements.txt /opt/bitnami/spark/

# Jalankan pip install untuk menginstal library
RUN pip install --no-cache-dir -r /opt/bitnami/spark/requirements.txt
