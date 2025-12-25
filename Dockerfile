# 1. Pakai Python versi ringan (Slim) biar hemat memori
FROM python:3.9-slim

# 2. Bikin folder kerja di dalam server namanya 'app'
WORKDIR /app

# 3. Update pip dan install library pendukung (biar cv2/pdf aman)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy file requirements.txt dulu (biar cache jalan)
COPY requirements.txt .

# 5. Install library Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy seluruh kodingan kamu ke server
COPY . .

# 7. Buka port 8501 (Jalur masuk Streamlit)
EXPOSE 8501

# 8. Cek kesehatan app (Healthcheck) - Optional tapi bagus buat Fly.io
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 9. Perintah untuk menyalakan aplikasi
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]