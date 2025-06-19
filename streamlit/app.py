import streamlit as st
import pandas as pd
from minio import Minio
import io

# Konfigurasi MinIO
MINIO_CLIENT = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)
BUCKET_NAME = "movies"

# --- FUNGSI CERDAS UNTUK MEMBACA DATA ---
@st.cache_data(show_spinner="Memuat data...")
def load_data_from_minio(object_name):
    """
    Fungsi ini membaca data dari MinIO.
    Ia otomatis mendeteksi apakah file tersebut .csv atau .parquet.
    """
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        file_data = io.BytesIO(response.read())
        
        if object_name.endswith('.csv'):
            return pd.read_csv(file_data)
        elif object_name.endswith('.parquet'):
            return pd.read_parquet(file_data)
        else:
            st.error(f"Format file tidak didukung: {object_name}")
            return None
    finally:
        if 'response' in locals() and response:
            response.close()
            response.release_conn()

# --- FUNGSI UNTUK MEMUAT HASIL SPARK (FOLDER) ---
@st.cache_data(show_spinner="Memuat hasil model...")
def load_spark_result(folder_path):
    """
    Fungsi ini membaca hasil Spark yang berupa folder berisi file Parquet.
    """
    try:
        # Mencari file parquet pertama di dalam folder
        objects = MINIO_CLIENT.list_objects(BUCKET_NAME, prefix=folder_path, recursive=True)
        parquet_object = next((obj for obj in objects if obj.object_name.endswith('.parquet')), None)

        if parquet_object:
            return load_data_from_minio(parquet_object.object_name)
        else:
            st.error(f"Tidak ada file Parquet yang ditemukan di folder: {folder_path}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal memuat hasil Spark dari {folder_path}: {e}")
        return pd.DataFrame()


# --- TAMPILAN UTAMA APLIKASI ---
st.set_page_config(layout="wide", page_title="Movie Recommendation App")
st.title("🎬 Aplikasi Rekomendasi Film")

# --- Navigasi ---
page = st.sidebar.selectbox("Pilih Halaman", ["Dashboard", "Movie Like This", "Rekomendasi per Usia"])

# Memuat data utama sekali saja
try:
    df_movies = load_data_from_minio("final_movies_dataset.csv")
except Exception as e:
    st.error(f"Gagal memuat dataset utama dari MinIO. Pastikan proses ingesti sudah dijalankan. Error: {e}")
    st.stop()


# --- KONTEN HALAMAN ---
if page == "Dashboard":
    st.header("Dashboard Film")
    st.write("Menampilkan film yang tersedia dalam dataset. Ini adalah data statis yang dibaca dari MinIO.")
    
    if not df_movies.empty:
        # Tampilkan dalam grid
        st.success(f"Menampilkan 20 dari {len(df_movies)} film.")
        cols = st.columns(5)
        for index, row in df_movies.head(20).iterrows():
            with cols[index % 5]:
                # Pastikan ada poster_filename sebelum menampilkan
                if pd.notna(row['poster_filename']):
                    st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/200x300.png?text=No+Poster", use_container_width=True)
                st.caption(row['name'])
    else:
        st.warning("Tidak ada data film untuk ditampilkan.")

elif page == "Movie Like This":
    st.header("Temukan Film yang Mirip (Content-Based)")
    st.info("Fitur ini sedang dalam pengembangan. Logika untuk menghitung kemiripan perlu ditambahkan.")
    # TODO: Muat data dari 'ml_results/similarities'
    # TODO: Buat dropdown untuk memilih film
    # TODO: Hitung kemiripan kosinus dari vektor fitur dan tampilkan hasilnya

elif page == "Rekomendasi per Usia":
    st.header("Rekomendasi Berdasarkan Target Usia")
    st.write("Prediksi target usia ini dihasilkan oleh Spark Job dan disimpan di MinIO.")
    
    df_audience = load_spark_result("ml_results/audience_predictions/")
    
    if not df_audience.empty:
        audience_select = st.selectbox("Pilih Target Audiens", df_audience['audience_age'].unique())
        
        filtered_movies = df_audience[df_audience['audience_age'] == audience_select]
        
        st.write(f"Menampilkan film untuk audiens: **{audience_select}**")
        cols = st.columns(5)
        for index, row in filtered_movies.head(10).iterrows():
            with cols[index % 5]:
                if pd.notna(row['poster_filename']):
                    st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/200x300.png?text=No+Poster", use_container_width=True)
                st.caption(row['name'])
    else:
        st.error("Gagal memuat data prediksi audiens. Pastikan Spark Job Batch telah berhasil dijalankan.")
