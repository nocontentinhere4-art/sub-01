FROM python:3.12-slim
WORKDIR /app
COPY requirements-server.txt .
# small 214-region matrices: BLAS threads only spin, and the CPU is shared with the screens' browser
ENV PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BROWSE=1
RUN pip install --no-cache-dir -r requirements-server.txt \
 && python -m playwright install --with-deps --only-shell chromium \
 && rm -rf /var/lib/apt/lists/*
COPY brain_sim.py sleep.py chat.py eye.py real_baseline.py life.py live_server.py diary.py research.py browse.py ./
COPY twin ./twin
COPY web ./web
COPY out/connectome.npz out/atlas_names.json ./out/
COPY out/rest ./out/rest
# /data is a persistent volume: sleep state, memory, nights, world, eye frames, browsing log
# BROWSE=1: his computer and phone screens show real web pages (headless Chromium); set BROWSE=0 to turn it off
CMD ["sh", "-c", "python live_server.py --host 0.0.0.0 --port ${PORT:-8080} --eye --trust-proxy --data-dir /data --frames-dir /data/frames ${EXTRA_ARGS:-}"]
