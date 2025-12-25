# 1. Pakai Python versi ringan (Slim)
FROM python:3.9-slim

# 2. Set folder kerja
WORKDIR /app

# 3. Install tools dasar Linux
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements.txt DULUAN
# (Penting: Pastikan file 'requirements.txt' sudah ada di folder project kamu!)
COPY requirements.txt .

# 5. Install Library Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy seluruh kodingan sisanya
COPY . .

# 7. Buka port 8501
EXPOSE 8501

# 8. Healthcheck (Cek kesehatan aplikasi)
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 9. Jalankan aplikasi
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]