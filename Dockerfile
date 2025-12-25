# ==========================================
# STAGE 1: Builder (Dapur Kotor)
# ==========================================
# Kita pakai image slim untuk membangun fondasi
FROM python:3.9-slim as builder

WORKDIR /app

# Install compiler (build-essential) CUMA di tahap ini.
# Ini dibutuhkan untuk meng-compile beberapa library Python (misal: pandas/numpy)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install library ke folder khusus (--user) biar gampang dipindah nanti
# --no-warn-script-location biar lognya gak berisik
RUN pip install --no-cache-dir --user --no-warn-script-location -r requirements.txt


# ==========================================
# STAGE 2: Final Image (Meja Saji Bersih)
# ==========================================
# Kita mulai lagi dari NOL dengan image slim yang bersih
FROM python:3.9-slim

WORKDIR /app

# Di tahap akhir, kita CUMA butuh 'curl' untuk healthcheck.
# Compiler 'build-essential' sudah TIDAK KITA INSTALL LAGI disini. Hemat ratusan MB!
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# COPY hasil installan Python dari Stage 1 (Builder) tadi
# Kita pindahkan dari /root/.local di builder ke /root/.local di image final
COPY --from=builder /root/.local /root/.local

# Beri tahu sistem agar membaca program dari folder hasil copy tadi
ENV PATH=/root/.local/bin:$PATH

# Copy kodingan aplikasimu
COPY . .

# Expose port & Healthcheck (Standar)
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Jalankan aplikasi
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
