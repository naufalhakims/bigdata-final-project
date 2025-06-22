import streamlit as st
import pandas as pd
from minio import Minio
import io
import os
import math

# --- KONFIGURASI DAN FUNGSI PEMBANTU ---
MINIO_CLIENT = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)
BUCKET_NAME = "movies"
PLACEHOLDER_IMAGE = "https://via.placeholder.com/200x300.png?text=Poster+Not+Found"

# --- FUNGSI-FUNGSI UNTUK MEMUAT DATA ---

@st.cache_data(show_spinner="Memuat data utama...")
def load_main_data(object_name):
    """Membaca data utama dari MinIO."""
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        file_data = io.BytesIO(response.read())
        if object_name.endswith('.csv'):
            return pd.read_csv(file_data)
        elif object_name.endswith('.parquet'):
            return pd.read_parquet(file_data)
        return None
    finally:
        if 'response' in locals() and response:
            response.close()
            response.release_conn()

@st.cache_data(show_spinner="Memuat hasil model...")
def load_spark_result(folder_path):
    """Membaca hasil Spark dari sebuah folder di MinIO."""
    try:
        objects = MINIO_CLIENT.list_objects(BUCKET_NAME, prefix=folder_path, recursive=True)
        parquet_object = next((obj for obj in objects if obj.object_name.endswith('.parquet')), None)
        if parquet_object:
            return load_main_data(parquet_object.object_name)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal memuat dari {folder_path}: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner="Mengecek poster yang tersedia...")
def get_available_posters(_bucket_name):
    """Mendapatkan set berisi semua nama file poster yang ada di MinIO."""
    poster_files = set()
    try:
        objects = MINIO_CLIENT.list_objects(_bucket_name, prefix="posters/", recursive=True)
        for obj in objects:
            if obj.object_name.endswith('.jpg'):
                poster_files.add(os.path.basename(obj.object_name))
    except Exception as e:
        st.error(f"Gagal mengambil daftar poster dari MinIO: {e}")
    return poster_files

# --- EKSEKUSI UTAMA APLIKASI ---

st.set_page_config(layout="wide", page_title="Movie Recommendation App")
st.title("🎬 Aplikasi Rekomendasi Film")

# Muat semua data yang dibutuhkan di awal
df_movies = load_main_data("final_movies_dataset.csv")
available_posters = get_available_posters(BUCKET_NAME) 

if df_movies is None or df_movies.empty:
    st.error("Gagal memuat dataset utama. Pastikan proses ingesti sudah berjalan.")
    st.stop()

# --- Navigasi ---
page = st.sidebar.selectbox("Pilih Halaman", ["Dashboard", "Movie Like This", "Rekomendasi per Usia"])

# --- KONTEN HALAMAN ---
if page == "Dashboard":
    st.header("Dashboard Film")
    st.write("Jelajahi atau cari semua film yang tersedia dalam dataset.")

    # --- KOTAK PENCARIAN ---
    search_query = st.text_input("Cari film berdasarkan judul:", placeholder="Ketik judul film di sini...")

    # Filter DataFrame berdasarkan input pencarian
    if search_query:
        df_filtered = df_movies[df_movies['name'].str.contains(search_query, case=False, na=False)]
    else:
        df_filtered = df_movies # Jika tidak ada input, tampilkan semua

    # --- LOGIKA PAGINASI ---
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 1

    ITEMS_PER_PAGE = 20
    total_movies = len(df_filtered)
    total_pages = math.ceil(total_movies / ITEMS_PER_PAGE) if total_movies > 0 else 1
    
    # Pastikan nomor halaman tidak melebihi total halaman setelah filtering
    if st.session_state.page_number > total_pages:
        st.session_state.page_number = 1

    start_idx = (st.session_state.page_number - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    df_page = df_filtered.iloc[start_idx:end_idx]

    if not df_page.empty:
        st.info(f"Menampilkan film {start_idx + 1} - {min(start_idx + len(df_page), total_movies)} dari {total_movies} hasil.")
        
        for i in range(0, len(df_page), 5):
            cols = st.columns(5)
            row_data = df_page.iloc[i:i+5]
            for j, (_, row) in enumerate(row_data.iterrows()):
                with cols[j]:
                    if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                        st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                    else:
                        st.image(PLACEHOLDER_IMAGE, use_container_width=True)
                    
                    date_val = int(row['date']) if pd.notna(row['date']) else 'N/A'
                    st.caption(f"{row['name']} ({date_val})")
    else:
        st.warning("Tidak ada film yang cocok dengan pencarian Anda.")
        
    # --- Tombol Navigasi Paginasi ---
    if total_movies > ITEMS_PER_PAGE:
        st.write("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Sebelumnya", disabled=(st.session_state.page_number <= 1)):
                st.session_state.page_number -= 1
                st.rerun()
        with col2:
            st.markdown(f"<div style='text-align: center;'>Halaman {st.session_state.page_number} dari {total_pages}</div>", unsafe_allow_html=True)
        with col3:
            if st.button("Berikutnya ➡️", disabled=(st.session_state.page_number >= total_pages)):
                st.session_state.page_number += 1
                st.rerun()

# (Kode untuk halaman lain tidak diubah dan tetap sama)
elif page == "Movie Like This":
    # ... (kode dari versi sebelumnya)
    st.header("Temukan Film yang Mirip (Content-Based)")
    df_recs = load_spark_result("ml_results/content_recommendations/")

    if not df_recs.empty:
        movies_with_recs_ids = df_recs['id'].tolist()
        df_selectable_movies = df_movies[df_movies['id'].isin(movies_with_recs_ids)]
        movie_list = df_selectable_movies['name'].tolist()

        selected_movie_name = st.selectbox(
            "Pilih film (hanya film dengan hasil rekomendasi yang ditampilkan):", 
            movie_list
        )
        
        if selected_movie_name:
            selected_movie_id = df_selectable_movies[df_selectable_movies['name'] == selected_movie_name]['id'].iloc[0]
            recommendations = df_recs[df_recs['id'] == selected_movie_id]
            
            if not recommendations.empty:
                rec_ids = recommendations['recommendations'].iloc[0]
                st.subheader(f"Film yang mirip dengan '{selected_movie_name}':")
                rec_movies_details = df_movies[df_movies['id'].isin(rec_ids)]
                
                cols = st.columns(len(rec_movies_details) if len(rec_movies_details) > 0 else 1)
                for i, (_, row) in enumerate(rec_movies_details.iterrows()):
                    with cols[i]:
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                            st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                        else:
                            st.image(PLACEHOLDER_IMAGE, use_container_width=True)
                        st.caption(row['name'])
            else:
                 st.warning("Tidak ditemukan rekomendasi untuk film ini.")
    else:
        st.error("Gagal memuat data rekomendasi. Pastikan Spark Job Batch telah berhasil dijalankan.")


elif page == "Rekomendasi per Usia":
    # ... (kode dari versi sebelumnya)
    st.header("Rekomendasi Berdasarkan Target Usia")
    df_audience = load_spark_result("ml_results/audience_predictions/")
    
    if not df_audience.empty:
        audience_select = st.selectbox("Pilih Target Audiens", df_audience['audience_age'].unique())
        filtered_movies = df_audience[df_audience['audience_age'] == audience_select]
        
        st.write(f"Menampilkan film untuk audiens: **{audience_select}**")
        
        for i in range(0, min(len(filtered_movies), 10), 5):
            cols = st.columns(5)
            row_data = filtered_movies.iloc[i:i+5]
            for j, (_, row) in enumerate(row_data.iterrows()):
                with cols[j]:
                    if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                        st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                    else:
                        st.image(PLACEHOLDER_IMAGE, use_container_width=True)
                    st.caption(row['name'])
    else:
        st.error("Gagal memuat data prediksi audiens.")
