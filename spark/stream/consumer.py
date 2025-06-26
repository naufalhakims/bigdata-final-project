# File: spark/stream/consumer.py (Versi Final dengan Model ML)
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, concat_ws, split
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.ml import PipelineModel # Untuk memuat model
import redis

# Path tempat model disimpan
MODEL_PATH = "s3a://movies/ml_models/vectorizer_pipeline_model"

def get_spark_session():
    return SparkSession.builder \
        .appName("RealtimeFeatureEngineering") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.path.style.access", True) \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def process_and_save(df, epoch_id, model):
    """Fungsi yang akan dieksekusi untuk setiap micro-batch."""
    if df.count() == 0:
        return

    print(f"--- Memproses batch ke-{epoch_id} ---")
    
    # Pra-pemrosesan teks yang sama dengan saat training
    df = df.na.fill("", subset=["description", "genre", "theme"])
    df = df.withColumn("tags", concat_ws(" ", col("description"), col("genre"), col("theme")))
    df = df.withColumn("tags", split(col("tags"), " "))
    
    # Gunakan model yang sudah dilatih untuk membuat fitur (HANYA TRANSFORM)
    featured_df = model.transform(df)
    
    # Ambil hasil (nama film dan vektor fiturnya)
    results_to_save = featured_df.select("name", "features").collect()

    # Tulis ke Redis dari driver
    try:
        r = redis.Redis(host='redis', port=6379, db=0)
        print(f"Menulis {len(results_to_save)} hasil fitur ke Redis...")
        for row in results_to_save:
            # Simpan nama film dan representasi string dari vektornya
            # Kita menggunakan ZADD untuk membuat sorted set, skornya adalah timestamp
            r.zadd("processed_movies_log", {f"{row['name']}: {row['features']}" : int(time.time())})
            # Batasi log di Redis hanya menyimpan 20 entri terbaru
            if r.zcard("processed_movies_log") > 20:
                r.zremrangebyrank("processed_movies_log", 0, 0)
    except Exception as e:
        print(f"Gagal menulis ke Redis: {e}")

def main():
    import time
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("Memuat model pipeline yang sudah dilatih dari MinIO...")
    try:
        # Muat model terlatih sekali di awal
        pipeline_model = PipelineModel.load(MODEL_PATH)
        print("✅ Model berhasil dimuat.")
    except Exception as e:
        print(f"❌ GAGAL memuat model dari {MODEL_PATH}. Pastikan skrip training sudah dijalankan. Error: {e}")
        return

    # Skema untuk parsing data JSON dari Kafka
    schema = StructType([
        StructField("name", StringType(), True),
        StructField("description", StringType(), True),
        StructField("genre", StringType(), True),
        StructField("theme", StringType(), True),
    ])

    # Baca stream dari Kafka
    df_stream = spark.readStream.format("kafka").option("kafka.bootstrap.servers", "kafka:29092").option("subscribe", "movie_views").load()
    df_parsed = df_stream.select(from_json(col("value").cast("string"), schema).alias("data")).select("data.*")

    # Gunakan foreachBatch untuk memproses setiap micro-batch
    query = df_parsed.writeStream.foreachBatch(lambda df, epoch_id: process_and_save(df, epoch_id, pipeline_model)).start()

    print("Consumer siap memproses data streaming dengan model ML...")
    query.awaitTermination()

if __name__ == "__main__":
    main()