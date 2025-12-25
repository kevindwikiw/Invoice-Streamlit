# 1. Pakai Python versi ringan (Slim)
FROM python:3.9-slim

# 2. Set folder kerja
WORKDIR /app

# 3. Update pip & Install tools dasar
# PERBAIKAN: Kita hapus 'software-properties-common' yang bikin error tadi
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements.txt DULUAN
COPY requirements.txt .

# 5. Install Library Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy seluruh kodingan
COPY . .

# 7. Buka port
EXPOSE 8501

# 8. Cek kesehatan app
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 9. Jalankan aplikasi
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]