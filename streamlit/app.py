# File: streamlit/app.py (Versi Final Gabungan Semua Fitur)

import streamlit as st
import pandas as pd
from minio import Minio
import redis
import time
import io
import pickle
import os
import math
import numpy as np

# --- KONFIGURASI KONEKSI ---
try:
    MINIO_CLIENT = Minio("minio:9000", access_key="minioadmin", secret_key="minioadmin", secure=False)
    BUCKET_NAME = "movies"
except Exception as e:
    st.error(f"Gagal menginisialisasi MinIO Client: {e}")

try:
    REDIS_CLIENT = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    REDIS_CLIENT.ping() # Cek koneksi
    redis_status = "Terhubung"
except Exception:
    redis_status = "Gagal Terhubung"

PLACEHOLDER_IMAGE = "https://via.placeholder.com/200x300.png?text=Poster+Not+Found"

# --- FUNGSI-FUNGSI PEMUATAN DATA (DENGAN CACHING) ---

@st.cache_data(show_spinner="Memuat model rekomendasi batch...")
def load_model_from_minio(object_name):
    """Membaca file model dari MinIO. Otomatis deteksi .pkl atau .npy."""
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        data_stream = io.BytesIO(response.read())
        data_stream.seek(0)
        
        if object_name.endswith('.pkl'):
            return pickle.load(data_stream)
        elif object_name.endswith('.npy'):
            return np.load(data_stream)
        return None
    except Exception:
        return None

@st.cache_data(show_spinner="Memuat dataset utama...")
def load_main_csv_data(object_name="final_movies_dataset.csv"):
    """Membaca data CSV utama dari MinIO untuk detail film."""
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        return pd.read_csv(io.BytesIO(response.read()))
    except Exception:
        return pd.DataFrame()
    finally:
        if 'response' in locals() and response: response.close(); response.release_conn()

@st.cache_data(show_spinner="Mengecek ketersediaan poster...")
def get_available_posters(_bucket_name):
    """Mendapatkan set nama file poster yang ada di MinIO."""
    try:
        return {os.path.basename(obj.object_name) for obj in MINIO_CLIENT.list_objects(_bucket_name, prefix="posters/", recursive=True) if obj.object_name.endswith('.jpg')}
    except Exception:
        return set()

# --- INISIALISASI APLIKASI ---

st.set_page_config(layout="wide", page_title="Movie Data Platform")
st.sidebar.title("🎬 Movie Data Platform")
st.sidebar.info(f"Status Redis: **{redis_status}**")

# --- NAVIGASI ---
page = st.sidebar.selectbox(
    "Pilih Halaman",
    ["Dashboard & Pencarian", "Rekomendasi Film (Batch)", "Live Feature Engineering (Streaming)"]
)

# ==============================================================================
# HALAMAN 1: DASHBOARD & PENCARIAN
# ==============================================================================
if page == "Dashboard & Pencarian":
    st.header("Dashboard dan Pencarian Film")
    full_movies_df = load_main_csv_data()
    available_posters = get_available_posters(BUCKET_NAME)

    if full_movies_df.empty:
        st.error("Data film utama tidak ditemukan. Pastikan proses ingesti sudah berjalan.")
    else:
        search_query = st.text_input("Cari film berdasarkan judul:", "")
        df_filtered = full_movies_df[full_movies_df['name'].str.contains(search_query, case=False, na=False)] if search_query else full_movies_df

        if 'page_number' not in st.session_state or st.session_state.get('search_query', '') != search_query:
            st.session_state.page_number = 1
            st.session_state.search_query = search_query
        
        ITEMS_PER_PAGE = 20
        total_items, total_pages = len(df_filtered), math.ceil(len(df_filtered) / ITEMS_PER_PAGE) if len(df_filtered) > 0 else 1
        if st.session_state.page_number > total_pages: st.session_state.page_number = 1
        start_idx, end_idx = (st.session_state.page_number - 1) * ITEMS_PER_PAGE, st.session_state.page_number * ITEMS_PER_PAGE
        df_page = df_filtered.iloc[start_idx:end_idx]

        if not df_page.empty:
            st.info(f"Menampilkan film {start_idx + 1}-{min(end_idx, total_items)} dari {total_items} hasil.")
            for i in range(0, len(df_page), 5):
                cols = st.columns(5)
                for j, (_, row) in enumerate(df_page.iloc[i:i+5].iterrows()):
                    with cols[j]:
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                            st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True, caption=row['name'])
                        else:
                            st.image(PLACEHOLDER_IMAGE, use_container_width=True, caption=row['name'])
        else:
            st.warning("Tidak ada film yang cocok dengan pencarian Anda.")

        if total_items > ITEMS_PER_PAGE:
            st.write("---"); col1, col2, col3 = st.columns([1, 2, 1])
            if col1.button("⬅️ Sebelumnya", disabled=(st.session_state.page_number <= 1)):
                st.session_state.page_number -= 1; st.rerun()
            col2.markdown(f"<div style='text-align: center;'>Halaman {st.session_state.page_number} dari {total_pages}</div>", unsafe_allow_html=True)
            if col3.button("Berikutnya ➡️", disabled=(st.session_state.page_number >= total_pages)):
                st.session_state.page_number += 1; st.rerun()

# ==============================================================================
# HALAMAN 2: REKOMENDASI FILM (BATCH)
# ==============================================================================
elif page == "Rekomendasi Film (Batch)":
    st.header("Temukan Film yang Mirip (Model Batch)")
    st.write("Model ini dibuat menggunakan Scikit-learn pada 5.000 data.")

    model_movies_df = load_model_from_minio("ml_results/sklearn_model/movies_df.pkl")
    cosine_sim = load_model_from_minio("ml_results/sklearn_model/similarity_matrix.npy")
    full_movies_df = load_main_csv_data()
    available_posters = get_available_posters(BUCKET_NAME)

    if model_movies_df is not None and cosine_sim is not None:
        movie_list = sorted(model_movies_df['name'].tolist())
        selected_movie = st.selectbox("Pilih sebuah film untuk menemukan yang serupa:", movie_list)

        if st.button("Dapatkan Rekomendasi"):
            st.subheader(f"Rekomendasi film yang mirip dengan '{selected_movie}':")
            try:
                idx = model_movies_df[model_movies_df['name'] == selected_movie].index[0]
                sim_scores = sorted(list(enumerate(cosine_sim[idx])), key=lambda x: x[1], reverse=True)
                movie_indices = [i[0] for i in sim_scores[1:6]]
                
                recommended_movies_info = model_movies_df.iloc[movie_indices]
                final_recs_df = pd.merge(recommended_movies_info, full_movies_df[['id', 'poster_filename', 'name']], on='id', how='left')

                cols = st.columns(5)
                for i, (_, row) in enumerate(final_recs_df.iterrows()):
                     with cols[i]:
                        display_name = row.get('name_y', row['name_x']) 
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                            st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True, caption=display_name)
                        else:
                            st.image(PLACEHOLDER_IMAGE, use_container_width=True, caption=display_name)
            except Exception as e:
                st.error(f"Terjadi error: {e}")
    else:
        st.error("Gagal memuat model rekomendasi. Pastikan Spark Job (batch) telah berhasil dijalankan.")

# ==============================================================================
# HALAMAN 3: LIVE FEATURE ENGINEERING (STREAMING)
# ==============================================================================
elif page == "Live Feature Engineering (Streaming)":
    st.header("⚙️ Live Feature Engineering Dashboard")
    st.write("Dashboard ini menampilkan log film yang diproses secara real-time oleh Spark. Setiap film diubah menjadi vektor fitur menggunakan model yang sudah dilatih.")
    
    log_placeholder = st.empty()
    
    while True:
        if redis_status != "Terhubung":
            with log_placeholder.container():
                st.error("Koneksi ke Redis gagal. Tidak bisa menampilkan data live.")
            break
        try:
            logs = REDIS_CLIENT.zrange("processed_movies_log", 0, -1, desc=True)
            with log_placeholder.container():
                st.subheader("Log Film yang Baru Diproses (20 Terakhir)")
                if not logs:
                    st.warning("Menunggu data masuk dari Kafka producer...")
                else:
                    for log_entry in logs:
                        st.code(log_entry, language="text")
        except Exception as e:
            with log_placeholder.container():
                st.error(f"Terjadi error saat mengambil data dari Redis: {e}")
        time.sleep(2)