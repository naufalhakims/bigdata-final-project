FROM bitnami/spark:3.4
USER root
COPY requirements.txt /opt/bitnami/spark/
RUN pip install --no-cache-dir -r /opt/bitnami/spark/requirements.txt