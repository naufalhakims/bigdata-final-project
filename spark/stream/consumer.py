from pyspark.sql import SparkSession

def get_spark_session():
    # Konfigurasi sama, bisa ditambahkan package kafka
    return SparkSession.builder \
        .appName("MovieStreamConsumer") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0") \
        .getOrCreate()

def main():
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Baca dari Kafka
    df_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "movie_views") \
        .load()

    # Tampilkan di console (aksi paling sederhana)
    query = df_stream.selectExpr("CAST(value AS STRING)") \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .start()

    print("Menunggu stream dari Kafka...")
    query.awaitTermination()

if __name__ == "__main__":
    main()
