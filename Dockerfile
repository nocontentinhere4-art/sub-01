FROM python:3.12-slim
WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY brain_sim.py sleep.py chat.py eye.py real_baseline.py life.py live_server.py diary.py research.py ./
COPY twin ./twin
COPY web ./web
COPY out/connectome.npz out/atlas_names.json ./out/
COPY out/rest ./out/rest
# /data is a persistent volume: sleep state, memory, nights, world, eye frames
CMD ["sh", "-c", "python live_server.py --host 0.0.0.0 --port ${PORT:-8080} --eye --trust-proxy --data-dir /data --frames-dir /data/frames ${EXTRA_ARGS:-}"]
