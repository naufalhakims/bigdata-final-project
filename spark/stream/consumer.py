from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, split as F_split, explode
from pyspark.sql.types import StructType, StructField, StringType
import redis

def process_batch(df, epoch_id):
    if df.count() > 0:
        genre_counts = df.withColumn("genre", col("genre").cast(StringType())) \
                         .filter(col("genre").isNotNull()) \
                         .withColumn("genre_array", F_split(col("genre"), "\\|")) \
                         .withColumn("genre_single", explode(col("genre_array"))) \
                         .groupBy("genre_single").count()
        results = genre_counts.collect()
        if results:
            try:
                r = redis.Redis(host='redis', port=6379, db=0)
                print(f"Menulis {len(results)} agregasi genre ke Redis...")
                for row in results:
                    r.hincrby("genre_counts", row['genre_single'], int(row['count']))
            except Exception as e: print(f"Gagal menulis ke Redis: {e}")
def main():
    spark = SparkSession.builder.appName("StreamConsumerToRedis").config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    schema = StructType([StructField("genre", StringType(), True)])
    df_stream = spark.readStream.format("kafka").option("kafka.bootstrap.servers", "kafka:29092").option("subscribe", "movie_views").load()
    df_parsed = df_stream.select(from_json(col("value").cast("string"), schema).alias("data")).select("data.*")
    query = df_parsed.writeStream.foreachBatch(process_batch).outputMode("update").start()
    print("Consumer streaming ke Redis dimulai..."); query.awaitTermination()
if __name__ == "__main__": main()