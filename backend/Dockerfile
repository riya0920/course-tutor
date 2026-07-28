FROM python:3.11-slim

WORKDIR /app

# System deps for PyMuPDF / chromadb wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Lean deps so the image fits Render's free 512 MB instance. Retrieval falls
# back to the hashing embedder + in-memory store (see app/rag.py). For full
# local quality (sentence-transformers + ChromaDB), install requirements.txt.
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

ENV DATA_DIR=/data
VOLUME ["/data"]

# Render/Railway inject $PORT; default to 8000 locally.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
