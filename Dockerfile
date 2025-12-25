# 1. Gunakan Python 3.13 Slim (Versi Terbaru & Paling Ringan)
FROM python:3.13-slim

# 2. Set Environment Variables
# (PYTHONDONTWRITEBYTECODE: Biar ga ada file .pyc sampah)
# (PYTHONUNBUFFERED: Biar log langsung muncul di terminal Fly.io)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Set Folder Kerja di dalam container
WORKDIR /app

# 4. Install Tools Dasar System
# (build-essential: kadang butuh buat compile library python tertentu)
# (curl: wajib buat Healthcheck)
# rm -rf: membersihkan cache apt biar size image tetep kecil
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy Requirements DULUAN (Teknik Caching Docker)
# Kalau code berubah tapi requirements ga berubah, docker ga perlu install ulang
COPY requirements.txt .

# 6. Install Library Python
# --no-cache-dir: Biar pip ga nyimpen file mentahan (Hemat space)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 7. Copy Seluruh Kodingan Aplikasi
COPY . .

# 8. Buka Port Default Streamlit
EXPOSE 8501

# 9. Healthcheck (Penting buat Fly.io ngecek app hidup/mati)
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 10. Jalankan Aplikasi
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
