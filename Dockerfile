# 1. Gunakan Python 3.13 Slim
FROM python:3.12-slim

# 2. Set Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Set Folder Kerja
WORKDIR /app

# 4. Install Tools Dasar System + LibPQ (WAJIB buat build psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy Requirements
COPY requirements.txt .

# 6. Install Library Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Setup Streamlit Secrets file (biar ga error kalau kosong)
RUN mkdir -p .streamlit && touch .streamlit/secrets.toml

# 7. Copy Seluruh Kodingan
COPY . .

# 8. Buka Port Default Streamlit
EXPOSE 8501

# 9. Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 10. Jalankan Aplikasi
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
