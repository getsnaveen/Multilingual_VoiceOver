# ---------- Base image ----------
FROM python:3.12-slim AS base

WORKDIR /app

# Only runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

# ---------- Builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl python3-venv \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
 && /opt/venv/bin/pip install --no-cache-dir torch==2.3.1+cpu -f https://download.pytorch.org/whl/torch_stable.html \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
 && find /opt/venv -type d -name "tests" -exec rm -rf {} + \
 && rm -rf /root/.cache/pip

# ---------- Final runtime ----------
FROM base

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app/main_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
